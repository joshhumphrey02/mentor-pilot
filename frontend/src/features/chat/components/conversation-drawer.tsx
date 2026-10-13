import { useQuery } from '@tanstack/react-query'
import { MessageSquarePlusIcon, SearchIcon } from 'lucide-react'
import { useState } from 'react'

import { CONTROL_CLASS } from '@/components/form/fields'
import { ResponsiveDialog } from '@/components/responsive-dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { useDebouncedValue } from '@/hooks/use-debounced-value'
import { cn } from '@/lib/utils'

import { conversationsQueryOptions, useCreateConversation } from '../api'

interface ConversationDrawerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  projectId: string
  activeId: string
  onSelect: (conversationId: string) => void
}

const dateFormat = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short' })

export function ConversationDrawer({
  open,
  onOpenChange,
  projectId,
  activeId,
  onSelect,
}: ConversationDrawerProps) {
  const [search, setSearch] = useState('')
  const term = useDebouncedValue(search.trim(), 250)
  const conversations = useQuery({
    ...conversationsQueryOptions(projectId, term),
    enabled: open,
  })
  const create = useCreateConversation(projectId)

  const choose = (conversationId: string) => {
    onSelect(conversationId)
    onOpenChange(false)
    setSearch('')
  }

  return (
    <ResponsiveDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Chats in this project"
      description="Start a fresh chat for a new topic. Your mentor remembers the project either way."
    >
      <div className="grid gap-3">
        <Button
          size="touch"
          disabled={create.isPending}
          onClick={async () => {
            const conversation = await create.mutateAsync().catch(() => null)
            if (conversation) choose(conversation.id)
          }}
        >
          <MessageSquarePlusIcon data-icon="inline-start" />
          New chat
        </Button>

        <div className="relative">
          <SearchIcon
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 left-3.5 size-4.5 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            type="search"
            aria-label="Search chats"
            placeholder="Search chats"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className={cn(CONTROL_CLASS, 'pl-10')}
          />
        </div>

        <ul className="grid max-h-[45dvh] gap-1 overflow-y-auto">
          {conversations.isPending &&
            [0, 1, 2].map((row) => <Skeleton key={row} className="h-14 rounded-xl" />)}
          {conversations.data?.length === 0 && (
            <li className="py-6 text-center text-sm text-muted-foreground">
              {term ? `No chats mention “${term}”.` : 'No chats yet.'}
            </li>
          )}
          {conversations.data?.map((conversation) => (
            <li key={conversation.id}>
              <button
                type="button"
                onClick={() => choose(conversation.id)}
                aria-current={conversation.id === activeId ? 'true' : undefined}
                className="flex min-h-14 w-full items-center justify-between gap-3 rounded-xl px-3 text-left hover:bg-muted aria-[current=true]:bg-secondary aria-[current=true]:text-secondary-foreground"
              >
                <span className="min-w-0 truncate font-medium">
                  {conversation.title || 'New chat'}
                </span>
                <time
                  dateTime={conversation.last_message_at}
                  className="shrink-0 text-sm text-muted-foreground"
                >
                  {dateFormat.format(new Date(conversation.last_message_at))}
                </time>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </ResponsiveDialog>
  )
}
