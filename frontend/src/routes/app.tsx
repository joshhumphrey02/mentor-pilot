import { createFileRoute, Link, Outlet } from '@tanstack/react-router'

import { Logo } from '@/components/brand/logo'
import { navFor } from '@/features/app-shell/nav'
import { useUser } from '@/features/auth/api'
import { requireOnboardedUser } from '@/features/auth/guards'

export const Route = createFileRoute('/app')({
  beforeLoad: requireOnboardedUser,
  component: AppLayout,
})

/**
 * The signed-in frame: a sidebar from `md` up, and on phones a bottom tab bar,
 * where the four destinations sit under the thumb.
 */
function AppLayout() {
  const items = navFor(useUser().role)
  return (
    <div className="min-h-dvh md:grid md:grid-cols-[15rem_minmax(0,1fr)]">
      <aside className="sticky top-0 hidden h-dvh flex-col border-r bg-sidebar p-4 md:flex">
        <Link to="/app" className="rounded-lg px-2 py-1.5" aria-label="Mentor Pilot home">
          <Logo />
        </Link>
        <nav aria-label="Main" className="mt-8 grid gap-1">
          {items.map(({ to, label, icon: Icon, exact }) => (
            <Link
              key={to}
              to={to}
              activeOptions={{ exact }}
              className="flex h-11 items-center gap-3 rounded-xl px-3 font-medium text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground data-[status=active]:bg-sidebar-accent data-[status=active]:text-sidebar-accent-foreground"
            >
              <Icon aria-hidden="true" className="size-5" />
              {label}
            </Link>
          ))}
        </nav>
      </aside>

      <div className="flex min-h-dvh min-w-0 flex-col">
        <header className="pt-safe md:hidden">
          <div className="flex h-14 items-center px-safe">
            <Logo />
          </div>
        </header>
        {/* Bottom padding clears the fixed tab bar (4rem) plus the home indicator. */}
        <main
          id="main"
          className="mx-auto w-full max-w-3xl flex-1 px-safe pt-4 pb-[calc(5.5rem+env(safe-area-inset-bottom))] md:px-8 md:pt-10 md:pb-12"
        >
          <Outlet />
        </main>
      </div>

      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-40 border-t bg-background/95 pb-safe backdrop-blur md:hidden"
      >
        <ul className="mx-auto grid h-16 max-w-md auto-cols-fr grid-flow-col">
          {items.map(({ to, label, icon: Icon, exact }) => (
            <li key={to}>
              <Link
                to={to}
                activeOptions={{ exact }}
                className="group flex h-full flex-col items-center justify-center gap-1 text-xs font-medium text-muted-foreground data-[status=active]:text-primary"
              >
                <span className="grid h-7 w-14 place-items-center rounded-full transition-colors group-data-[status=active]:bg-secondary">
                  <Icon aria-hidden="true" className="size-5" />
                </span>
                {label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  )
}
