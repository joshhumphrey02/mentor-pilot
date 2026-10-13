import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, type Schemas } from '@/lib/api/client'
import { unwrap } from '@/lib/api/errors'

export type User = Schemas['UserOut']
export type OnboardingInput = Schemas['OnboardingRequest']

/**
 * The signed-in user, or null for a visitor. Fetching it is how the app learns
 * whether there is a session: the auth cookies are httpOnly, so JavaScript
 * cannot simply look.
 */
export const meQueryOptions = queryOptions({
  queryKey: ['me'] as const,
  queryFn: async (): Promise<User | null> => {
    const result = await api.GET('/api/v1/users/me')
    if (result.response.status === 401) return null
    return unwrap(result)
  },
  staleTime: 5 * 60_000,
  retry: false,
})

export const useMe = () => useQuery(meQueryOptions)

/** For screens behind the auth guard, where the user is known to exist. */
export function useUser(): User {
  const { data } = useMe()
  if (!data) throw new Error('useUser must be rendered inside an authenticated route')
  return data
}

function useSetMe() {
  const queryClient = useQueryClient()
  return (user: User | null) => queryClient.setQueryData(meQueryOptions.queryKey, user)
}

export const authProvidersQueryOptions = queryOptions({
  queryKey: ['auth', 'providers'] as const,
  queryFn: async () => unwrap(await api.GET('/api/v1/auth/providers')),
  staleTime: Infinity,
})

export function useLogin() {
  const setMe = useSetMe()
  return useMutation({
    mutationFn: async (body: Schemas['LoginRequest']) =>
      unwrap(await api.POST('/api/v1/auth/login', { body })),
    onSuccess: setMe,
  })
}

export function useRegister() {
  return useMutation({
    mutationFn: async (body: Schemas['RegisterRequest']) =>
      unwrap(await api.POST('/api/v1/auth/register', { body })),
  })
}

export function useVerifyEmail() {
  const setMe = useSetMe()
  return useMutation({
    mutationFn: async (token: string) =>
      unwrap(await api.POST('/api/v1/auth/verify-email', { body: { token } })),
    onSuccess: setMe,
  })
}

export function useResendVerification() {
  return useMutation({
    mutationFn: async (email: string) =>
      unwrap(await api.POST('/api/v1/auth/resend-verification', { body: { email } })),
  })
}

export function useForgotPassword() {
  return useMutation({
    mutationFn: async (email: string) =>
      unwrap(await api.POST('/api/v1/auth/forgot-password', { body: { email } })),
  })
}

export function useResetPassword() {
  const setMe = useSetMe()
  return useMutation({
    mutationFn: async (body: Schemas['ResetPasswordRequest']) =>
      unwrap(await api.POST('/api/v1/auth/reset-password', { body })),
    // The server signs out every session when a password is reset.
    onSuccess: () => setMe(null),
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => unwrap(await api.POST('/api/v1/auth/logout')),
    // Drop everything cached for the previous user, not just their profile.
    onSettled: () => {
      forgetOfflineData()
      queryClient.clear()
      queryClient.setQueryData(meQueryOptions.queryKey, null)
    },
  })
}

export function useCompleteOnboarding() {
  const setMe = useSetMe()
  return useMutation({
    mutationFn: async (body: OnboardingInput) =>
      unwrap(await api.POST('/api/v1/users/me/onboarding', { body })),
    onSuccess: setMe,
  })
}

export function useUpdateProfile() {
  const setMe = useSetMe()
  return useMutation({
    mutationFn: async (body: Schemas['UserUpdate']) =>
      unwrap(await api.PATCH('/api/v1/users/me', { body })),
    onSuccess: setMe,
  })
}

export function useDeleteAccount() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: Schemas['DeleteAccountRequest']) =>
      unwrap(await api.POST('/api/v1/users/me/delete', { body })),
    onSuccess: () => {
      forgetOfflineData()
      queryClient.clear()
      queryClient.setQueryData(meQueryOptions.queryKey, null)
    },
  })
}

/**
 * Removes the conversations the service worker saved for offline reading.
 * On a shared phone the next person must not find the last learner's chats.
 */
function forgetOfflineData() {
  if ('caches' in window) void caches.delete('api-recent').catch(() => undefined)
}

export const schoolSearchQueryOptions = (query: string) =>
  queryOptions({
    queryKey: ['schools', query] as const,
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/schools', { params: { query: { q: query, limit: 6 } } })),
    staleTime: 60_000,
  })
