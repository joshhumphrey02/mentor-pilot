import {
  FolderKanbanIcon,
  HomeIcon,
  type LucideIcon,
  ShieldCheckIcon,
  UserRoundIcon,
  UsersRoundIcon,
} from 'lucide-react'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  exact?: boolean
}

const HOME: NavItem = { to: '/app', label: 'Home', icon: HomeIcon, exact: true }
const PROJECTS: NavItem = { to: '/app/projects', label: 'Projects', icon: FolderKanbanIcon }
const MENTOR: NavItem = { to: '/app/mentor', label: 'Mentor', icon: UsersRoundIcon }
const PROFILE: NavItem = { to: '/app/profile', label: 'Profile', icon: UserRoundIcon }
const ADMIN: NavItem = { to: '/app/admin', label: 'Admin', icon: ShieldCheckIcon }

/** Each role gets the destinations that mean something to it, never more than four. */
export function navFor(role: string): NavItem[] {
  if (role === 'mentor') return [{ ...MENTOR, label: 'Requests' }, PROFILE]
  if (role === 'admin') return [HOME, PROJECTS, ADMIN, PROFILE]
  return [HOME, PROJECTS, MENTOR, PROFILE]
}
