import { FolderKanbanIcon, HomeIcon, type LucideIcon, UserRoundIcon, UsersRoundIcon } from 'lucide-react'

export const NAV_ITEMS: { to: string; label: string; icon: LucideIcon; exact?: boolean }[] = [
  { to: '/app', label: 'Home', icon: HomeIcon, exact: true },
  { to: '/app/projects', label: 'Projects', icon: FolderKanbanIcon },
  { to: '/app/mentor', label: 'Mentor', icon: UsersRoundIcon },
  { to: '/app/profile', label: 'Profile', icon: UserRoundIcon },
]
