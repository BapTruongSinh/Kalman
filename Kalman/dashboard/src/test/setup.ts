import '@testing-library/jest-dom'

// Recharts' ResponsiveContainer relies on ResizeObserver which is absent in jsdom.
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver

// Recharts reads element dimensions; provide non-zero layout stubs.
Object.defineProperty(HTMLElement.prototype, 'getBoundingClientRect', {
  value: () => ({ width: 800, height: 300, x: 0, y: 0, top: 0, left: 0, right: 800, bottom: 300, toJSON: () => ({}) }),
  configurable: true,
})
Object.defineProperty(HTMLElement.prototype, 'clientWidth', {
  get: () => 800,
  configurable: true,
})
Object.defineProperty(HTMLElement.prototype, 'clientHeight', {
  get: () => 300,
  configurable: true,
})
