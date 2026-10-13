"""Runs a conversation turn: learner message in, streamed mentor reply out.

A turn runs in its own task, decoupled from the HTTP response that watches it.
If the learner's connection drops (a phone losing signal mid-answer), the turn
still finishes and is saved; the client finds the message by id when it comes
back, instead of the answer being lost.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import timedelta

import structlog
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sse_starlette import ServerSentEvent

from app.ai.blocks import (
    Block,
    CalloutBlock,
    ErrorBlock,
    MarkdownBlock,
    SuggestedRepliesBlock,
    dump_blocks,
)
from app.ai.prompts.builder import LearnerContext, ProjectContext, build_system_prompt
from app.ai.service import AIService, UsageContext
from app.ai.stream_parser import (
    BlockComplete,
    BlockDelta,
    BlockStart,
    BlockStreamParser,
    ParserEvent,
)
from app.ai.types import (
    ChatMessage,
    Done,
    ErrorEvent,
    ModerationResult,
    TextDelta,
    Usage,
    UsageEvent,
)
from app.core.errors import AppError, ConflictError
from app.core.time import utcnow
from app.models import (
    Conversation,
    Message,
    MessageRole,
    MessageStatus,
    ModerationFlag,
    Project,
    User,
)
from app.schemas.chat import (
    BlockCompleteEvent,
    BlockStartEvent,
    ConversationEvent,
    ConversationOut,
    DoneEvent,
    MessageOut,
    MessageStartEvent,
    TextDeltaEvent,
    UsageOut,
)
from app.services import projects

logger = structlog.get_logger(__name__)

# A reply still "streaming" after this long belongs to a turn that died.
TURN_TIMEOUT = timedelta(minutes=3)
# How many recent messages the model sees. Older context reaches it through
# the project's rolling summary instead.
HISTORY_LIMIT = 40
TITLE_MAX_LENGTH = 60

REDIRECT: list[Block] = [
    MarkdownBlock(
        text="I can't help with that one, but I'm here for your project. "
        "What would you like to work on next?"
    ),
    SuggestedRepliesBlock(replies=["Help me find a project idea", "Where was I up to?"]),
]
UNCHECKED = ErrorBlock(
    code="moderation_unavailable",
    text="I couldn't check that message just now. Please send it again in a moment.",
    retryable=True,
)
EMPTY_REPLY = ErrorBlock(
    code="empty_reply",
    text="I lost my train of thought there. Could you send that again?",
    retryable=True,
)

TITLE_SYSTEM = """\
You name conversations between a school learner and their science project mentor. Given the \
start of a conversation, reply with a short title of two to six words that says what it is \
about. Reply with the title only: no quotes, no full stop, no preamble."""


@dataclass
class Turn:
    """Everything the background task needs, captured while the request is live."""

    conversation_id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    school_id: uuid.UUID | None
    assistant_message_id: uuid.UUID
    user_message_id: uuid.UUID
    user_message: MessageOut | None  # None when regenerating: nothing new to show
    user_text: str
    learner: LearnerContext
    check_input: bool
    needs_title: bool


def _sse(name: str, payload: BaseModel) -> ServerSentEvent:
    return ServerSentEvent(event=name, data=payload.model_dump_json())


def learner_context(user: User) -> LearnerContext:
    profile = user.student_profile
    return LearnerContext(
        first_name=user.full_name.split()[0] if user.full_name.strip() else "",
        grade=profile.grade if profile else None,
        education_level=profile.education_level if profile else "high_school",
        province=profile.province if profile else None,
        school=profile.school.name if profile and profile.school else None,
        interests=list(profile.interests) if profile else [],
        learning_style=profile.learning_style if profile else None,
        language=user.preferred_language,
    )


def visible_text(blocks: list[Block]) -> str:
    """The words a learner would read, for moderation."""
    parts: list[str] = []
    for block in blocks:
        if isinstance(block, MarkdownBlock | CalloutBlock):
            parts.append(block.text)
        elif isinstance(block, SuggestedRepliesBlock):
            parts.extend(block.replies)
    return "\n".join(parts)


class ChatService:
    def __init__(self, ai: AIService) -> None:
        self.ai = ai
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        # Strong references: asyncio only keeps weak ones, and a turn must not
        # be garbage-collected halfway through.
        self._tasks: set[asyncio.Task[None]] = set()

    def bind(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def shutdown(self) -> None:
        """Lets turns that are mid-answer finish and save before the app exits."""
        if self._tasks:
            await asyncio.wait(self._tasks, timeout=20)
        for task in self._tasks:
            task.cancel()

    # --- starting a turn (inside the request) ---------------------------------

    async def _claim(
        self, session: AsyncSession, user: User, conversation_id: uuid.UUID
    ) -> tuple[Conversation, Project]:
        """Loads the conversation and makes sure no other turn is running in it."""
        conversation, project = await projects.get_conversation(session, user, conversation_id)
        # Locking the row makes two simultaneous sends queue up here, so the
        # check below cannot be passed by both.
        await session.execute(
            select(Conversation.id).where(Conversation.id == conversation.id).with_for_update()
        )
        running = (
            await session.scalars(
                select(Message).where(
                    Message.conversation_id == conversation.id,
                    Message.status == MessageStatus.STREAMING.value,
                )
            )
        ).all()
        for message in running:
            if utcnow() - message.created_at < TURN_TIMEOUT:
                raise ConflictError(
                    "Your mentor is still replying. Wait for that to finish first.",
                    code="turn_in_progress",
                )
            message.status = MessageStatus.ERROR.value
        return conversation, project

    def _placeholder(self, conversation: Conversation) -> Message:
        return Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT.value,
            status=MessageStatus.STREAMING.value,
        )

    async def begin_turn(
        self, session: AsyncSession, user: User, conversation_id: uuid.UUID, text: str
    ) -> Turn:
        conversation, project = await self._claim(session, user, conversation_id)
        is_first = await projects.count_messages(session, conversation.id) == 0

        user_message = Message(
            conversation_id=conversation.id,
            role=MessageRole.USER.value,
            blocks=dump_blocks([MarkdownBlock(text=text)]),
            raw=text,
        )
        session.add(user_message)
        await session.flush()  # so the user message gets the lower sequence number
        assistant = self._placeholder(conversation)
        session.add(assistant)
        conversation.last_message_at = project.last_activity_at = utcnow()
        await session.commit()
        await session.refresh(user_message)

        return Turn(
            conversation_id=conversation.id,
            project_id=project.id,
            user_id=user.id,
            school_id=user.student_profile.school_id if user.student_profile else None,
            assistant_message_id=assistant.id,
            user_message_id=user_message.id,
            user_message=MessageOut.model_validate(user_message),
            user_text=text,
            learner=learner_context(user),
            check_input=True,
            needs_title=is_first and not conversation.title,
        )

    async def begin_regeneration(
        self, session: AsyncSession, user: User, conversation_id: uuid.UUID
    ) -> Turn:
        """Replaces the mentor's latest reply with a fresh attempt at the same message."""
        conversation, project = await self._claim(session, user, conversation_id)
        latest = (
            await session.scalars(
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.seq.desc())
                .limit(2)
            )
        ).all()
        if (
            len(latest) < 2
            or latest[0].role != MessageRole.ASSISTANT.value
            or latest[1].role != MessageRole.USER.value
            or latest[1].status != MessageStatus.COMPLETE.value
        ):
            raise AppError("There is no reply to try again.", code="nothing_to_regenerate")
        old_reply, user_message = latest
        await session.delete(old_reply)
        assistant = self._placeholder(conversation)
        session.add(assistant)
        await session.commit()

        return Turn(
            conversation_id=conversation.id,
            project_id=project.id,
            user_id=user.id,
            school_id=user.student_profile.school_id if user.student_profile else None,
            assistant_message_id=assistant.id,
            user_message_id=user_message.id,
            user_message=None,
            user_text=user_message.raw,
            learner=learner_context(user),
            # It passed moderation when it was first sent.
            check_input=False,
            needs_title=False,
        )

    # --- running it (background task) ------------------------------------------

    async def stream(self, turn: Turn) -> AsyncIterator[ServerSentEvent]:
        """Starts the turn and relays its events. Safe to abandon at any point."""
        queue: asyncio.Queue[ServerSentEvent | None] = asyncio.Queue()
        task = asyncio.create_task(self._guarded(turn, queue))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        while (event := await queue.get()) is not None:
            yield event

    async def _guarded(self, turn: Turn, queue: asyncio.Queue[ServerSentEvent | None]) -> None:
        try:
            await self._run(turn, queue)
        except Exception:
            logger.exception("chat.turn_crashed", conversation_id=str(turn.conversation_id))
            await self._fail(turn, queue)
        finally:
            queue.put_nowait(None)

    async def _fail(self, turn: Turn, queue: asyncio.Queue[ServerSentEvent | None]) -> None:
        """Last resort: never leave a message stuck as "streaming"."""
        assert self._session_factory is not None  # noqa: S101
        block = ErrorBlock(
            code="internal",
            text="Something went wrong on our side. Please try again.",
            retryable=True,
        )
        try:
            async with self._session_factory() as session:
                message = await session.get(Message, turn.assistant_message_id)
                if message is None:
                    return
                message.blocks = dump_blocks([block])
                message.status = MessageStatus.ERROR.value
                await session.commit()
                queue.put_nowait(
                    _sse("done", DoneEvent(message=MessageOut.model_validate(message)))
                )
        except Exception:
            logger.exception("chat.turn_failure_not_recorded")

    async def _run(self, turn: Turn, queue: asyncio.Queue[ServerSentEvent | None]) -> None:
        assert self._session_factory is not None  # noqa: S101
        emit = queue.put_nowait
        emit(
            _sse(
                "message_start",
                MessageStartEvent(
                    user_message=turn.user_message, assistant_message_id=turn.assistant_message_id
                ),
            )
        )

        async with self._session_factory() as session:
            assistant = await session.get(Message, turn.assistant_message_id)
            if assistant is None:
                return

            if turn.check_input:
                verdict = await self.ai.moderate(turn.user_text)
                if self.ai.blocks(verdict):
                    blocks = await self._withhold_input(session, turn, verdict)
                    for index, block in enumerate(blocks):
                        emit(_sse("block_complete", BlockCompleteEvent(index=index, block=block)))
                    await self._finish(
                        session,
                        turn,
                        assistant,
                        blocks,
                        raw="",
                        usage=Usage(),
                        # An outage is not the learner's fault, so it reads as an
                        # error they can retry, not as a refusal.
                        status=MessageStatus.COMPLETE if verdict.checked else MessageStatus.ERROR,
                        emit=emit,
                    )
                    return

            project = await session.get(Project, turn.project_id)
            system = build_system_prompt(
                turn.learner,
                ProjectContext(
                    title=project.title if project else "", memory=project.memory if project else ""
                ),
            )
            history = await self._history(session, turn.conversation_id, before_seq=assistant.seq)

            parser = BlockStreamParser()
            raw: list[str] = []
            usage = Usage()
            failure: ErrorEvent | None = None
            refused = False

            def relay(events: list[ParserEvent]) -> None:
                for event in events:
                    if isinstance(event, BlockStart):
                        emit(
                            _sse(
                                "block_start",
                                BlockStartEvent(index=event.index, type=event.block_type),
                            )
                        )
                    elif isinstance(event, BlockDelta):
                        emit(_sse("text_delta", TextDeltaEvent(index=event.index, text=event.text)))
                    elif isinstance(event, BlockComplete):
                        emit(
                            _sse(
                                "block_complete",
                                BlockCompleteEvent(index=event.index, block=event.block),
                            )
                        )

            async for ai_event in self.ai.stream_chat(
                messages=history,
                system=system,
                task="chat",
                context=UsageContext(
                    user_id=turn.user_id, school_id=turn.school_id, project_id=turn.project_id
                ),
            ):
                if isinstance(ai_event, TextDelta):
                    raw.append(ai_event.text)
                    relay(parser.feed(ai_event.text))
                elif isinstance(ai_event, UsageEvent):
                    usage = ai_event.usage
                elif isinstance(ai_event, Done):
                    refused = ai_event.stop_reason == "refusal"
                elif isinstance(ai_event, ErrorEvent):
                    failure = ai_event
            relay(parser.finish())

            blocks = list(parser.blocks)
            text = "".join(raw)
            status = MessageStatus.COMPLETE

            if failure is not None:
                # Keep whatever arrived before the failure, and say what happened.
                error = ErrorBlock(
                    code=failure.code, text=failure.message, retryable=failure.retryable
                )
                emit(_sse("block_complete", BlockCompleteEvent(index=len(blocks), block=error)))
                blocks.append(error)
                status = MessageStatus.ERROR
            elif refused:
                blocks, text = list(REDIRECT), ""
            elif not blocks:
                blocks, text, status = [EMPTY_REPLY], "", MessageStatus.ERROR
            else:
                verdict = await self.ai.moderate(visible_text(blocks))
                if self.ai.blocks(verdict):
                    session.add(
                        ModerationFlag(
                            user_id=turn.user_id,
                            conversation_id=turn.conversation_id,
                            message_id=assistant.id,
                            direction="output",
                            categories=verdict.categories,
                            checked=verdict.checked,
                            content=text,
                        )
                    )
                    logger.warning("chat.output_withheld", categories=verdict.categories)
                    blocks, text = list(REDIRECT), ""

            await self._finish(
                session, turn, assistant, blocks, raw=text, usage=usage, status=status, emit=emit
            )

            if turn.needs_title and status is MessageStatus.COMPLETE and text:
                conversation = await self._name_conversation(session, turn, text)
                if conversation is not None:
                    emit(
                        _sse(
                            "conversation",
                            ConversationEvent(
                                conversation=ConversationOut.model_validate(conversation)
                            ),
                        )
                    )

    async def _withhold_input(
        self, session: AsyncSession, turn: Turn, verdict: ModerationResult
    ) -> list[Block]:
        user_message = await session.get(Message, turn.user_message_id)
        if user_message is not None:
            # Blocked messages are never sent to the model, now or as history.
            user_message.status = MessageStatus.BLOCKED.value
        session.add(
            ModerationFlag(
                user_id=turn.user_id,
                conversation_id=turn.conversation_id,
                message_id=turn.user_message_id,
                direction="input",
                categories=verdict.categories,
                checked=verdict.checked,
                content=turn.user_text,
            )
        )
        logger.warning(
            "chat.input_withheld", categories=verdict.categories, checked=verdict.checked
        )
        return list(REDIRECT) if verdict.checked else [UNCHECKED]

    async def _finish(
        self,
        session: AsyncSession,
        turn: Turn,
        assistant: Message,
        blocks: list[Block],
        *,
        raw: str,
        usage: Usage,
        status: MessageStatus,
        emit: Callable[[ServerSentEvent], None],
    ) -> None:
        assistant.blocks = dump_blocks(blocks)
        assistant.raw = raw
        assistant.status = status.value
        assistant.provider = self.ai.registry.active_name
        assistant.model = self.ai.model_for("chat")
        assistant.input_tokens = usage.input_tokens
        assistant.output_tokens = usage.output_tokens
        now = utcnow()
        conversation = await session.get(Conversation, turn.conversation_id)
        if conversation is not None:
            conversation.last_message_at = now
        project = await session.get(Project, turn.project_id)
        if project is not None:
            project.last_activity_at = now
        await session.commit()

        emit(
            _sse(
                "usage",
                UsageOut(input_tokens=usage.input_tokens, output_tokens=usage.output_tokens),
            )
        )
        emit(_sse("done", DoneEvent(message=MessageOut.model_validate(assistant))))

    async def _history(
        self, session: AsyncSession, conversation_id: uuid.UUID, *, before_seq: int
    ) -> list[ChatMessage]:
        rows = (
            await session.scalars(
                select(Message)
                .where(
                    Message.conversation_id == conversation_id,
                    Message.seq < before_seq,
                    Message.status == MessageStatus.COMPLETE.value,
                    # Canned replies (redirects) have no raw text and are not
                    # something the model said, so they are left out.
                    Message.raw != "",
                )
                .order_by(Message.seq.desc())
                .limit(HISTORY_LIMIT)
            )
        ).all()
        history = [
            ChatMessage(
                role="user" if row.role == MessageRole.USER.value else "assistant", text=row.raw
            )
            for row in reversed(rows)
        ]
        # A conversation sent to a model has to open with the user.
        while history and history[0].role != "user":
            history.pop(0)
        return history

    async def _name_conversation(
        self, session: AsyncSession, turn: Turn, reply: str
    ) -> Conversation | None:
        conversation = await session.get(Conversation, turn.conversation_id)
        if conversation is None or conversation.title:
            return None
        result = await self.ai.complete(
            task="title",
            system=TITLE_SYSTEM,
            messages=[
                ChatMessage(
                    role="user",
                    text=f"Learner: {turn.user_text[:500]}\n\nMentor: {reply[:500]}",
                )
            ],
            max_tokens=256,
            context=UsageContext(
                user_id=turn.user_id, school_id=turn.school_id, project_id=turn.project_id
            ),
        )
        title = " ".join(result.text.split()).strip(" \"'.")
        if result.error is not None or not title:
            # Still better than "Untitled": the learner's own opening words.
            title = " ".join(turn.user_text.split())
        conversation.title = title[:TITLE_MAX_LENGTH].rstrip()
        await session.commit()
        return conversation


async def list_messages(
    session: AsyncSession, conversation: Conversation, *, before: int | None, limit: int
) -> tuple[list[Message], int | None]:
    """A page of messages, oldest first, plus a cursor for the page before it."""
    statement = select(Message).where(Message.conversation_id == conversation.id)
    if before is not None:
        statement = statement.where(Message.seq < before)
    rows = list(
        (await session.scalars(statement.order_by(Message.seq.desc()).limit(limit + 1))).all()
    )
    has_more = len(rows) > limit
    page = list(reversed(rows[:limit]))
    await _expire_stale(session, page)
    return page, (page[0].seq if has_more and page else None)


async def _expire_stale(session: AsyncSession, messages: list[Message]) -> None:
    """A reply left "streaming" by a crashed turn is shown as failed, not as a spinner."""
    stale = [
        message
        for message in messages
        if message.status == MessageStatus.STREAMING.value
        and utcnow() - message.created_at >= TURN_TIMEOUT
    ]
    for message in stale:
        message.status = MessageStatus.ERROR.value
        if not message.blocks:
            message.blocks = dump_blocks(
                [
                    ErrorBlock(
                        code="interrupted",
                        text="This reply was interrupted. Please try again.",
                        retryable=True,
                    )
                ]
            )
    if stale:
        await session.commit()


async def get_message(session: AsyncSession, user: User, message_id: uuid.UUID) -> Message:
    message = await session.get(Message, message_id)
    if message is None:
        raise AppError("We couldn't find that message.", code="message_not_found", status_code=404)
    # Raises the same not-found error if the conversation is not theirs.
    await projects.get_conversation(session, user, message.conversation_id)
    await _expire_stale(session, [message])
    return message


async def set_feedback(session: AsyncSession, message: Message, value: int) -> Message:
    if message.role != MessageRole.ASSISTANT.value:
        raise AppError("Feedback is for the mentor's replies.", code="invalid_feedback_target")
    message.feedback = value or None
    await session.commit()
    return message
