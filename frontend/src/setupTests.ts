import '@testing-library/jest-dom/vitest'

// jsdom has no IntersectionObserver. Report every observed element as
// immediately visible so lazy-rendered content mounts synchronously in tests.
class MockIntersectionObserver implements IntersectionObserver {
  readonly root = null
  readonly rootMargin = ''
  readonly thresholds: ReadonlyArray<number> = []
  constructor(private callback: IntersectionObserverCallback) {}
  observe(target: Element) {
    this.callback([{ isIntersecting: true, target } as IntersectionObserverEntry], this)
  }
  unobserve() {}
  disconnect() {}
  takeRecords(): IntersectionObserverEntry[] { return [] }
}
// @ts-expect-error partial polyfill is sufficient for tests
global.IntersectionObserver = MockIntersectionObserver
