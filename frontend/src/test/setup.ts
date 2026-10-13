import '@testing-library/jest-dom/vitest'

import { cleanup, configure } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// jsdom does not implement matchMedia; components that adapt to screen size
// or colour scheme need it to exist. Tests run as a narrow, light-mode screen.
window.matchMedia ??= vi.fn((query: string) => ({
  matches: false,
  media: query,
  onchange: null,
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  addListener: vi.fn(),
  removeListener: vi.fn(),
  dispatchEvent: vi.fn(),
})) as unknown as typeof window.matchMedia

// Radix measures its controls with ResizeObserver, which jsdom also lacks.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// Nor IntersectionObserver. With no layout everything counts as on screen, so
// content that waits to be scrolled into view appears straight away.
globalThis.IntersectionObserver ??= class {
  readonly root = null
  readonly rootMargin = ''
  readonly thresholds = []
  private readonly callback: IntersectionObserverCallback
  constructor(callback: IntersectionObserverCallback) {
    this.callback = callback
  }
  observe(target: Element) {
    queueMicrotask(() =>
      this.callback(
        [{ isIntersecting: true, intersectionRatio: 1, target } as IntersectionObserverEntry],
        this,
      ),
    )
  }
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return []
  }
}

window.scrollTo = vi.fn() as unknown as typeof window.scrollTo
// jsdom has no layout, so element scrolling is a no-op there.
Element.prototype.scrollTo = vi.fn() as unknown as typeof Element.prototype.scrollTo

// Whole-app tests load routes and lazy chunks on demand. A second is not
// always enough on a busy machine, and a slow test is better than a flaky one.
configure({ asyncUtilTimeout: 5000 })

afterEach(() => {
  cleanup()
  localStorage.clear()
  document.documentElement.className = ''
})
