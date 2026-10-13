import { useQueryClient, useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { ArrowLeftIcon, ChevronDownIcon, HistoryIcon, NotebookPenIcon, XIcon } from 'lucide-react'
import { useCallback, useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { useUser } from '@/features/auth/api'
import { requireOnboardedUser } from '@/features/auth/guards'
import { type Conversation, projectQueryOptions, refreshProjects } from '@/features/chat/api'
import { Composer } from '@/features/chat/components/composer'
import { ConversationDrawer } from '@/features/chat/components/conversation-drawer'
import { MessageList } from '@/features/chat/components/message-list'
import { StageSheet } from '@/features/chat/components/stage-sheet'
import { Welcome } from '@/features/chat/components/welcome'
import { useChat } from '@/features/chat/use-chat'
import { WorkspaceContext } from '@/features/chat/workspace-context'
import { usePinBlock } from '@/features/workspace/api'
import { WorkspacePanel } from '@/features/workspace/workspace-panel'
import { Drawer, DrawerContent, DrawerDescription, DrawerTitle } from '@/components/ui/drawer'
import { errorMessage } from '@/lib/api/errors'
import { toast } from 'sonner'
import { PATHWAY_STAGES, stagePosition } from '@/features/pathway/stages'
import { useVisualViewportHeight } from '@/hooks/use-visual-viewport'

export const Route = createFileRoute('/project/$projectId')({
  validateSearch: (search: Record<string, unknown>): { c?: string } => ({
    c: typeof search.c === 'string' ? search.c : undefined,
  }),
  beforeLoad: requireOnboardedUser,
  loader: ({ context, params }) =>
    context.queryClient.ensureQueryData(projectQueryOptions(params.projectId)),
  component: WorkspacePage,
})

function WorkspacePage() {
  const { projectId } = Route.useParams()
  const { c: selected } = Route.useSearch()
  const { data: project } = useSuspenseQuery(projectQueryOptions(projectId))
  const conversationId = selected ?? project.latest_conversation?.id

  if (!conversationId) {
    return (
      <main id="main" className="grid min-h-dvh place-items-center px-safe text-center">
        <div>
          <p className="text-muted-foreground">This project has no chats yet.</p>
          <Button asChild size="touch" className="mt-4">
            <Link to="/app/projects">Back to projects</Link>
          </Button>
        </div>
      </main>
    )
  }

  // Keyed by conversation so switching chats starts from a clean slate.
  return <Workspace key={conversationId} conversationId={conversationId} />
}

function Workspace({ conversationId }: { conversationId: string }) {
  const { projectId } = Route.useParams()
  const user = useUser()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: project } = useSuspenseQuery(projectQueryOptions(projectId))
  const [historyOpen, setHistoryOpen] = useState(false)
  const viewportHeight = useVisualViewportHeight()

  const onConversationChange = useCallback(
    (_conversation: Conversation) =>
      queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'conversations'] }),
    [queryClient, projectId],
  )

  // The mentor's tools can rename the project, move its stage or tick its
  // checklist during a turn, so refresh what is on screen when one ends.
  const onTurnEnd = useCallback(() => void refreshProjects(queryClient), [queryClient])

  const chat = useChat({ conversationId, onConversationChange, onTurnEnd })
  const [stagesOpen, setStagesOpen] = useState(false)
  const [toolsOpen, setToolsOpen] = useState(false)
  const pin = usePinBlock(projectId)
  const { mutateAsync: pinBlock } = pin
  const onSave = useCallback(
    async (messageId: string, blockIndex: number) => {
      try {
        await pinBlock({ message_id: messageId, block_index: blockIndex })
      } catch (error) {
        toast.error(errorMessage(error))
        throw error
      }
    },
    [pinBlock],
  )
  const stage = stagePosition(project.current_stage)
  const workspace = useMemo(
    () => ({
      projectId,
      currentStage: project.current_stage,
      send: chat.send,
      busy: chat.isResponding,
    }),
    [projectId, project.current_stage, chat.send, chat.isResponding],
  )
  const latest = chat.messages.at(-1)
  const suggestions =
    latest?.role === 'assistant'
      ? (latest.blocks.find((block) => block.type === 'suggested_replies')?.replies ?? [])
      : []

  return (
    <div
      // On wide screens the project tools sit beside the chat.
      className="grid h-dvh grid-cols-1 overflow-hidden lg:grid-cols-[minmax(0,1fr)_24rem]"
      // While the on-screen keyboard is open this is shorter than 100dvh.
      style={viewportHeight ? { height: viewportHeight } : undefined}
    >
    <div className="flex min-h-0 min-w-0 flex-col overflow-hidden">
      <header className="border-b bg-background pt-safe">
        <div className="mx-auto flex h-16 w-full max-w-3xl items-center gap-1 px-2 sm:px-4">
          <Button asChild variant="ghost" size="icon-touch">
            <Link to="/app/projects" aria-label="Back to projects">
              <ArrowLeftIcon />
            </Link>
          </Button>
          {/* The stage track, collapsed to one line. Tapping it opens the pathway. */}
          <button
            type="button"
            onClick={() => setStagesOpen(true)}
            aria-haspopup="dialog"
            className="min-w-0 flex-1 rounded-xl px-2 py-1 text-left hover:bg-muted"
          >
            <h1 className="truncate font-sans text-base font-semibold tracking-normal">
              {project.title}
            </h1>
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <span className="truncate">
                Stage {stage.number} of {PATHWAY_STAGES.length} · {stage.title}
              </span>
              <ChevronDownIcon aria-hidden="true" className="size-3.5 shrink-0" />
            </span>
            <span
              aria-hidden="true"
              className="mt-1 flex gap-0.5"
            >
              {PATHWAY_STAGES.map((item, index) => (
                <span
                  key={item.key}
                  className={`h-1 flex-1 rounded-full ${index < stage.number ? 'bg-primary' : 'bg-border'}`}
                />
              ))}
            </span>
          </button>
          <Button
            variant="ghost"
            size="icon-touch"
            className="lg:hidden"
            aria-label="Checklist, logbook, saved items and data"
            onClick={() => setToolsOpen(true)}
          >
            <NotebookPenIcon />
          </Button>
          <Button
            variant="ghost"
            size="icon-touch"
            aria-label="Chats in this project"
            onClick={() => setHistoryOpen(true)}
          >
            <HistoryIcon />
          </Button>
        </div>
      </header>

      <WorkspaceContext value={workspace}>
      <main id="main" className="flex min-h-0 flex-1 flex-col">
        {chat.isLoading ? (
          <div role="status" className="grid flex-1 place-items-center text-muted-foreground">
            Loading your chat…
          </div>
        ) : chat.loadError ? (
          <div role="alert" className="grid flex-1 place-items-center px-safe text-center">
            <p className="text-muted-foreground">
              We couldn't load this chat. Check your connection and refresh the page.
            </p>
          </div>
        ) : (
          <MessageList
            messages={chat.messages}
            pending={chat.pending}
            onRegenerate={chat.regenerate}
            onQuickReply={chat.send}
            onSave={onSave}
            empty={<Welcome name={user.full_name.split(' ')[0] || 'there'} onPick={chat.send} />}
          />
        )}

        {chat.error && (
          <div
            role="alert"
            className="mx-auto flex w-full max-w-3xl items-center gap-2 px-safe pb-2 text-sm"
          >
            <p className="flex-1 rounded-xl border border-danger/30 bg-danger-soft px-3 py-2 text-danger">
              {chat.error}
            </p>
            <Button
              variant="ghost"
              size="icon-touch"
              aria-label="Dismiss"
              onClick={chat.dismissError}
            >
              <XIcon />
            </Button>
          </div>
        )}

        <Composer
          projectId={projectId}
          onSend={chat.send}
          busy={chat.isResponding}
          suggestions={suggestions}
        />
      </main>
      </WorkspaceContext>
    </div>

      <aside aria-label="Project tools" className="hidden min-h-0 border-l bg-sidebar p-4 lg:block">
        <WorkspaceContext value={workspace}>
          <WorkspacePanel projectId={projectId} />
        </WorkspaceContext>
      </aside>

      {/* The same tools as a bottom sheet on phones and tablets. */}
      <Drawer open={toolsOpen} onOpenChange={setToolsOpen}>
        <DrawerContent className="h-[88dvh] lg:hidden">
          <DrawerTitle className="sr-only">Project tools</DrawerTitle>
          <DrawerDescription className="sr-only">
            Your checklist, logbook, saved items and data.
          </DrawerDescription>
          <div className="min-h-0 flex-1 px-4 pt-2 pb-[max(1rem,env(safe-area-inset-bottom))]">
            <WorkspaceContext value={workspace}>
              <WorkspacePanel projectId={projectId} />
            </WorkspaceContext>
          </div>
        </DrawerContent>
      </Drawer>

      <StageSheet open={stagesOpen} onOpenChange={setStagesOpen} projectId={projectId} />

      <ConversationDrawer
        open={historyOpen}
        onOpenChange={setHistoryOpen}
        projectId={projectId}
        activeId={conversationId}
        onSelect={(id) =>
          navigate({ to: '/project/$projectId', params: { projectId }, search: { c: id } })
        }
      />
    </div>
  )
}
