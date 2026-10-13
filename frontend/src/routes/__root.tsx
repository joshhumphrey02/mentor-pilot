import type { QueryClient } from '@tanstack/react-query'
import { createRootRouteWithContext, Link, Outlet } from '@tanstack/react-router'
import { CompassIcon, TriangleAlertIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Toaster } from '@/components/ui/sonner'

export interface RouterContext {
  queryClient: QueryClient
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
  notFoundComponent: NotFound,
  errorComponent: RouteError,
})

function RootLayout() {
  return (
    <>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
      >
        Skip to content
      </a>
      <Outlet />
      <Toaster position="top-center" />
    </>
  )
}

function NotFound() {
  return (
    <main id="main" className="grid min-h-dvh place-items-center px-safe py-16">
      <div className="max-w-sm text-center">
        <CompassIcon aria-hidden="true" className="mx-auto size-10 text-primary" />
        <h1 className="mt-4 text-2xl font-semibold">This page is off the map</h1>
        <p className="mt-2 text-muted-foreground">
          The link may be old, or the page may have moved. Let's get you back on course.
        </p>
        <Button asChild size="touch" className="mt-6">
          <Link to="/">Back to home</Link>
        </Button>
      </div>
    </main>
  )
}

function RouteError({ reset }: { reset: () => void }) {
  return (
    <main id="main" className="grid min-h-dvh place-items-center px-safe py-16">
      <div className="max-w-sm text-center">
        <TriangleAlertIcon aria-hidden="true" className="mx-auto size-10 text-warning" />
        <h1 className="mt-4 text-2xl font-semibold">Something went wrong</h1>
        <p className="mt-2 text-muted-foreground">
          That wasn't supposed to happen. Check your connection and try again.
        </p>
        <Button size="touch" className="mt-6" onClick={reset}>
          Try again
        </Button>
      </div>
    </main>
  )
}
