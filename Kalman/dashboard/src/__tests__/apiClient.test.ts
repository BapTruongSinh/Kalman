import { describe, expect, it, vi, afterEach } from 'vitest'
import { fetchRuns, fetchSeries, fetchMetrics } from '../api/client'

const RUNS = [{ id: 1, name: 'run-1', run_type: 'live', status: 'completed', created_at: '2024-01-01T00:00:00Z' }]

const SERIES_RESP = {
  run_id: 1,
  run_name: 'run-1',
  run_status: 'completed',
  total_cycles: 2,
  returned: 2,
  data: [],
}

const METRICS_RESP = {
  run_id: 1,
  run_name: 'run-1',
  slices: {},
}

function mockFetch(payload: unknown, ok = true) {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok,
    json: () => Promise.resolve(payload),
    status: ok ? 200 : 500,
  } as Response)
}

describe('API client', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('fetchRuns', () => {
    it('calls /api/runs/', async () => {
      mockFetch(RUNS)
      const result = await fetchRuns()
      expect(result).toEqual(RUNS)
      expect(global.fetch).toHaveBeenCalledWith('/api/runs/')
    })

    it('throws on non-ok response', async () => {
      mockFetch({}, false)
      await expect(fetchRuns()).rejects.toThrow('HTTP 500')
    })
  })

  describe('fetchSeries', () => {
    it('calls correct URL without params', async () => {
      mockFetch(SERIES_RESP)
      await fetchSeries(1)
      expect(global.fetch).toHaveBeenCalledWith('/api/runs/1/series/')
    })

    it('appends online slice param', async () => {
      mockFetch(SERIES_RESP)
      await fetchSeries(1, { slice: 'online' })
      const url = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
      expect(url).toContain('slice=online')
    })

    it('appends limit and stride params', async () => {
      mockFetch(SERIES_RESP)
      await fetchSeries(1, { limit: 500, stride: 2 })
      const url = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
      expect(url).toContain('limit=500')
      expect(url).toContain('stride=2')
    })
  })

  describe('fetchMetrics', () => {
    it('calls correct URL', async () => {
      mockFetch(METRICS_RESP)
      await fetchMetrics(42)
      expect(global.fetch).toHaveBeenCalledWith('/api/runs/42/metrics/')
    })
  })
})
