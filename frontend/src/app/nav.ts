import type { IconType } from 'react-icons'
import { LuBriefcase, LuDatabase, LuFileText, LuSlidersHorizontal } from 'react-icons/lu'

export type NavItem = { to: string; label: string; icon: IconType; pinned?: boolean }

export const navItems: NavItem[] = [
  { to: '/sources', label: 'Sources', icon: LuDatabase },
  { to: '/career', label: 'Career', icon: LuBriefcase },
  { to: '/documents', label: 'Documents', icon: LuFileText },
  { to: '/settings', label: 'Settings', icon: LuSlidersHorizontal, pinned: true },
]
