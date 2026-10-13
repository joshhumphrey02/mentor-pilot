import { createFileRoute, Outlet } from '@tanstack/react-router'

// A pathless layout: groups the sign-in pages without adding a URL segment.
export const Route = createFileRoute('/_auth')({ component: Outlet })
