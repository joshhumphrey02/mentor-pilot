import type { QueryClient } from '@tanstack/react-query'
import { redirect } from '@tanstack/react-router'

import { meQueryOptions, type User } from './api'

interface GuardArgs {
  context: { queryClient: QueryClient }
  location: { href: string }
}

const loadMe = (queryClient: QueryClient) => queryClient.ensureQueryData(meQueryOptions)

/** Learners must finish onboarding before using the app; staff have none to do. */
export const needsOnboarding = (user: User) => user.role === 'student' && !user.is_onboarded

/** For the app itself: signed in, and onboarded if a learner. */
export async function requireOnboardedUser({ context, location }: GuardArgs) {
  const user = await loadMe(context.queryClient)
  if (!user) throw redirect({ to: '/login', search: { redirect: location.href } })
  if (needsOnboarding(user)) throw redirect({ to: '/onboarding' })
  return { user }
}

/** For onboarding: signed in, whatever the onboarding state. */
export async function requireUser({ context, location }: GuardArgs) {
  const user = await loadMe(context.queryClient)
  if (!user) throw redirect({ to: '/login', search: { redirect: location.href } })
  return { user }
}

/** For login and register: someone already signed in goes straight to the app. */
export async function requireGuest({ context }: GuardArgs) {
  const user = await loadMe(context.queryClient)
  if (user) throw redirect({ to: needsOnboarding(user) ? '/onboarding' : '/app' })
}

/**
 * Only follow `?redirect=` to a path inside this app. Without this check a
 * crafted login link could bounce a learner to another site after sign-in.
 */
export function safeRedirect(target: string | undefined): string | undefined {
  if (!target || !target.startsWith('/') || target.startsWith('//') || target.includes('\\')) {
    return undefined
  }
  return target
}
