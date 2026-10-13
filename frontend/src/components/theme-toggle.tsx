import { MonitorIcon, MoonIcon, SunIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { type Theme, useThemeStore } from '@/stores/theme'

const ORDER: Theme[] = ['system', 'light', 'dark']
const LABEL: Record<Theme, string> = { system: 'System', light: 'Light', dark: 'Dark' }
const ICON = { system: MonitorIcon, light: SunIcon, dark: MoonIcon } satisfies Record<Theme, unknown>

/** Cycles system → light → dark. One 44px button rather than a menu on phones. */
export function ThemeToggle() {
  const theme = useThemeStore((state) => state.theme)
  const setTheme = useThemeStore((state) => state.setTheme)
  const next = ORDER[(ORDER.indexOf(theme) + 1) % ORDER.length] ?? 'system'
  const Icon = ICON[theme]

  return (
    <Button
      variant="ghost"
      size="icon-touch"
      onClick={() => setTheme(next)}
      aria-label={`Theme: ${LABEL[theme]}. Switch to ${LABEL[next]}.`}
      title={`Theme: ${LABEL[theme]}`}
    >
      <Icon />
    </Button>
  )
}
