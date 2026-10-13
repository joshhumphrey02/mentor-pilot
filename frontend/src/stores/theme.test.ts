import { beforeEach, describe, expect, it } from 'vitest'

import { useThemeStore } from './theme'

describe('theme store', () => {
  beforeEach(() => useThemeStore.setState({ theme: 'system' }))

  it('applies the dark class and remembers the choice', () => {
    useThemeStore.getState().setTheme('dark')

    expect(document.documentElement).toHaveClass('dark')
    expect(localStorage.getItem('mp-theme')).toBe('dark')
    expect(useThemeStore.getState().theme).toBe('dark')
  })

  it('removes the dark class when switching back to light', () => {
    useThemeStore.getState().setTheme('dark')
    useThemeStore.getState().setTheme('light')

    expect(document.documentElement).not.toHaveClass('dark')
  })
})
