import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query'

import { api, type Schemas } from '@/lib/api/client'
import { unwrap } from '@/lib/api/errors'

export type MentorRequest = Schemas['MentorRequestOut']
export type MentorMessage = Schemas['MentorMessageOut']
export type MentorProfile = Schemas['MentorProfileOut']
export type HelpType = Schemas['MentorHandoffBlock']['help_types'][number]

export const HELP_TYPES: Record<HelpType, string> = {
  hardware_build: 'Building hardware',
  lab_access: 'Access to a lab',
  materials: 'Finding materials',
  coding: 'Coding help',
  expo_coaching: 'Expo coaching',
}

export const STATUS_LABELS: Record<MentorRequest['status'], string> = {
  pending: 'Looking for a mentor',
  matched: 'Mentor found',
  in_progress: 'In progress',
  completed: 'Completed',
  cancelled: 'Cancelled',
}

const byId = (requestId: string) => ({ params: { path: { request_id: requestId } } })

export const myRequestsQueryOptions = queryOptions({
  queryKey: ['mentor-requests'] as const,
  queryFn: async () => unwrap(await api.GET('/api/v1/mentor-requests')),
})

export const openRequestsQueryOptions = queryOptions({
  queryKey: ['mentor-requests', 'open'] as const,
  queryFn: async () => unwrap(await api.GET('/api/v1/mentors/open-requests')),
  retry: false,
})

export const mentorProfileQueryOptions = queryOptions({
  queryKey: ['mentor-profile'] as const,
  queryFn: async () => unwrap(await api.GET('/api/v1/mentors/me')),
})

export const threadQueryOptions = (requestId: string) =>
  queryOptions({
    queryKey: ['mentor-requests', requestId, 'messages'] as const,
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/mentor-requests/{request_id}/messages', byId(requestId))),
    // There is no push channel yet, so an open thread checks for new messages.
    refetchInterval: 15_000,
  })

export const usageQueryOptions = queryOptions({
  queryKey: ['usage'] as const,
  queryFn: async () => unwrap(await api.GET('/api/v1/users/me/usage')),
})

export const expoEventsQueryOptions = queryOptions({
  queryKey: ['expo-events'] as const,
  queryFn: async () => unwrap(await api.GET('/api/v1/expo-events')),
  staleTime: 60 * 60_000,
})

function useRefreshRequests() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: myRequestsQueryOptions.queryKey })
}

export function useRequestMentor(projectId: string) {
  const refresh = useRefreshRequests()
  return useMutation({
    mutationFn: async (body: Schemas['MentorRequestIn']) =>
      unwrap(
        await api.POST('/api/v1/projects/{project_id}/mentor-requests', {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
    onSuccess: refresh,
  })
}

export function useRequestAction() {
  const refresh = useRefreshRequests()
  return useMutation({
    mutationFn: async ({
      requestId,
      action,
    }: {
      requestId: string
      action: 'accept' | 'cancel' | 'in_progress' | 'completed'
    }) => {
      if (action === 'accept') {
        return unwrap(await api.POST('/api/v1/mentor-requests/{request_id}/accept', byId(requestId)))
      }
      if (action === 'cancel') {
        return unwrap(await api.POST('/api/v1/mentor-requests/{request_id}/cancel', byId(requestId)))
      }
      return unwrap(
        await api.POST('/api/v1/mentor-requests/{request_id}/status', {
          ...byId(requestId),
          body: { status: action },
        }),
      )
    },
    onSuccess: refresh,
  })
}

export function useSendThreadMessage(requestId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (text: string) =>
      unwrap(
        await api.POST('/api/v1/mentor-requests/{request_id}/messages', {
          ...byId(requestId),
          body: { text },
        }),
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: threadQueryOptions(requestId).queryKey }),
  })
}

export function useSaveMentorProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: Schemas['MentorProfileIn']) =>
      unwrap(await api.PUT('/api/v1/mentors/me', { body })),
    onSuccess: (profile) => queryClient.setQueryData(mentorProfileQueryOptions.queryKey, profile),
  })
}
