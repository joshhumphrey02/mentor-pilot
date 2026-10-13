import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query'

import { api, type Schemas } from '@/lib/api/client'
import { unwrap } from '@/lib/api/errors'

export type Project = Schemas['ProjectOut']
export type ProjectDetail = Schemas['ProjectDetail']
export type Conversation = Schemas['ConversationOut']
export type Message = Schemas['MessageOut']
export type Block = Message['blocks'][number]
export type StreamEvents = Schemas['ChatStreamEvents']

export const projectsQueryOptions = queryOptions({
  queryKey: ['projects'] as const,
  queryFn: async () => unwrap(await api.GET('/api/v1/projects')),
})

export const projectQueryOptions = (projectId: string) =>
  queryOptions({
    queryKey: ['projects', projectId] as const,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}', {
          params: { path: { project_id: projectId } },
        }),
      ),
  })

export const conversationsQueryOptions = (projectId: string, query = '') =>
  queryOptions({
    queryKey: ['projects', projectId, 'conversations', query] as const,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/conversations', {
          params: { path: { project_id: projectId }, query: { q: query } },
        }),
      ),
  })

export const messagesQueryOptions = (conversationId: string) =>
  queryOptions({
    queryKey: ['conversations', conversationId, 'messages'] as const,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/conversations/{conversation_id}/messages', {
          params: { path: { conversation_id: conversationId }, query: { limit: 100 } },
        }),
      ).messages,
    // The stream keeps this cache current; refetching mid-reply would fight it.
    staleTime: Infinity,
  })

export async function fetchMessage(messageId: string): Promise<Message> {
  return unwrap(
    await api.GET('/api/v1/messages/{message_id}', {
      params: { path: { message_id: messageId } },
    }),
  )
}

export function useCreateProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (title: string) =>
      unwrap(await api.POST('/api/v1/projects', { body: { title } })),
    onSuccess: (project) => {
      queryClient.setQueryData(projectQueryOptions(project.id).queryKey, project)
      void queryClient.invalidateQueries({ queryKey: projectsQueryOptions.queryKey, exact: true })
    },
  })
}

export function useCreateConversation(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST('/api/v1/projects/{project_id}/conversations', {
          params: { path: { project_id: projectId } },
          body: { title: '' },
        }),
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'conversations'] }),
  })
}

export function useFeedback(conversationId: string) {
  const queryClient = useQueryClient()
  const key = messagesQueryOptions(conversationId).queryKey
  return useMutation({
    mutationFn: async ({ messageId, value }: { messageId: string; value: -1 | 0 | 1 }) =>
      unwrap(
        await api.POST('/api/v1/messages/{message_id}/feedback', {
          params: { path: { message_id: messageId } },
          body: { value },
        }),
      ),
    // Optimistic: a thumbs-up should respond to the tap, not to the network.
    onMutate: async ({ messageId, value }) => {
      await queryClient.cancelQueries({ queryKey: key })
      const previous = queryClient.getQueryData(key)
      queryClient.setQueryData(key, (messages) =>
        messages?.map((message) =>
          message.id === messageId ? { ...message, feedback: value || null } : message,
        ),
      )
      return { previous }
    },
    onError: (_error, _variables, context) => queryClient.setQueryData(key, context?.previous),
  })
}

/** The readable text of a message, for copying. */
export function messageText(message: Pick<Message, 'blocks'>): string {
  return message.blocks
    .map((block) => (block.type === 'markdown' || block.type === 'callout' ? block.text : ''))
    .filter(Boolean)
    .join('\n\n')
}
