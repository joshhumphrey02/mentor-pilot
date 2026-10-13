import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query'

import { api } from '@/lib/api/client'
import { unwrap } from '@/lib/api/errors'

export type UsageGroup = 'day' | 'user' | 'school' | 'provider'

export const adminQueries = {
  usage: (groupBy: UsageGroup) =>
    queryOptions({
      queryKey: ['admin', 'usage', groupBy] as const,
      queryFn: async () =>
        unwrap(await api.GET('/api/v1/admin/usage', { params: { query: { group_by: groupBy } } })),
    }),
  users: (q: string) =>
    queryOptions({
      queryKey: ['admin', 'users', q] as const,
      queryFn: async () => unwrap(await api.GET('/api/v1/admin/users', { params: { query: { q } } })),
    }),
  schools: queryOptions({
    queryKey: ['admin', 'schools'] as const,
    queryFn: async () => unwrap(await api.GET('/api/v1/admin/schools')),
  }),
  mentors: queryOptions({
    queryKey: ['admin', 'mentors'] as const,
    queryFn: async () => unwrap(await api.GET('/api/v1/admin/mentors')),
  }),
  requests: queryOptions({
    queryKey: ['admin', 'requests'] as const,
    queryFn: async () => unwrap(await api.GET('/api/v1/admin/mentor-requests')),
  }),
  flags: queryOptions({
    queryKey: ['admin', 'flags'] as const,
    queryFn: async () => unwrap(await api.GET('/api/v1/admin/moderation')),
  }),
  providers: queryOptions({
    queryKey: ['admin', 'providers'] as const,
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/admin/ai/providers', { params: { query: { check: true } } })),
    staleTime: 60_000,
  }),
  stages: queryOptions({
    queryKey: ['admin', 'stages'] as const,
    queryFn: async () => unwrap(await api.GET('/api/v1/admin/stages')),
  }),
}

/** Runs an admin action, then refreshes every admin list. */
export function useAdminAction<Input>(action: (input: Input) => Promise<unknown>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: action,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin'] }),
  })
}

export const adminActions = {
  setUserActive: async ({ id, active }: { id: string; active: boolean }) =>
    unwrap(
      await api.PATCH('/api/v1/admin/users/{user_id}', {
        params: { path: { user_id: id } },
        body: { is_active: active },
      }),
    ),
  verifySchool: async ({ id, verified }: { id: string; verified: boolean }) =>
    unwrap(
      await api.PATCH('/api/v1/admin/schools/{school_id}', {
        params: { path: { school_id: id } },
        body: { is_verified: verified },
      }),
    ),
  approveMentor: async ({ id, approved }: { id: string; approved: boolean }) =>
    unwrap(
      await api.POST('/api/v1/admin/mentors/{user_id}/approval', {
        params: { path: { user_id: id } },
        body: { approved },
      }),
    ),
  assignMentor: async ({ requestId, mentorId }: { requestId: string; mentorId: string }) =>
    unwrap(
      await api.POST('/api/v1/admin/mentor-requests/{request_id}/assign', {
        params: { path: { request_id: requestId } },
        body: { mentor_id: mentorId },
      }),
    ),
  reviewFlag: async (id: string) =>
    unwrap(
      await api.POST('/api/v1/admin/moderation/{flag_id}/review', {
        params: { path: { flag_id: id } },
      }),
    ),
}
