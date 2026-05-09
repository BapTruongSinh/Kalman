import { describe, expect, it, vi, afterEach } from 'vitest'
import {
  fetchControlProfile,
  fetchLatestAMPCRecommendation,
  fetchMetrics,
  fetchRuns,
  fetchSeries,
  patchControlProfile,
  runAMPCRecommendation,
} from '../api/client'

const RUNS = [
  {
    id: 1,
    name: 'run-1',
    run_type: 'live',
    status: 'completed',
    greenhouse_id: 7,
    greenhouse_name: 'Greenhouse A',
    created_at: '2024-01-01T00:00:00Z',
  },
]

const SERIES_RESP = {
  run_id: 1,
  run_name: 'run-1',
  greenhouse_id: 7,
  greenhouse_name: 'Greenhouse A',
  run_status: 'completed',
  total_cycles: 2,
  returned: 2,
  data: [],
}

const METRICS_RESP = {
  run_id: 1,
  run_name: 'run-1',
  greenhouse_id: 7,
  greenhouse_name: 'Greenhouse A',
  slices: {},
}

const AMPC_RESP = {
  success: true,
  data: {
    id: 3,
    greenhouse_id: 7,
    mode: 'ampc',
    state_cycle_id: 9,
    run_id: 1,
    pump_seconds: 30,
    step_seconds: 300,
    predicted_soil_moisture: [55.2],
    target_band: { low: 55, high: 65 },
    cost: 1.2,
    safety_status: 'safe',
    reason: 'below_target_margin',
    bias_correction: 0.1,
    bias_window_count: 3,
    used_today_pump_seconds: 60,
    actuator: {
      enabled: false,
      executed: false,
      status: 'disabled',
      command: null,
      http_status_code: null,
      alert: null,
      error: null,
    },
    created_at: '2026-05-09T10:00:00Z',
  },
  error: null,
}

const PROFILE_RESP = {
  success: true,
  data: {
    id: 5,
    greenhouse_id: 7,
    crop_name: 'generic',
    crop_kc: 1,
    target_low: 55,
    target_high: 65,
    pump_max_seconds: 300,
    soft_daily_pump_cap_seconds: 1800,
    actuator_enabled: false,
    actuator_configured: false,
    created_at: '2026-05-09T10:00:00Z',
    updated_at: '2026-05-09T10:00:00Z',
  },
  error: null,
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

  describe('AMPC endpoints', () => {
    it('POSTs empty body to run recommendation endpoint', async () => {
      mockFetch(AMPC_RESP)
      await runAMPCRecommendation(7)
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/greenhouses/7/ampc/recommendations/',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: '{}',
        },
      )
    })

    it('POSTs token auth when provided', async () => {
      mockFetch(AMPC_RESP)
      await runAMPCRecommendation(7, { authToken: 'abc123' })
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/greenhouses/7/ampc/recommendations/',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: 'Token abc123',
          },
          body: '{}',
        },
      )
    })

    it('fetches latest recommendation endpoint', async () => {
      mockFetch(AMPC_RESP)
      await fetchLatestAMPCRecommendation(7)
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/greenhouses/7/ampc/recommendations/latest/',
      )
    })

    it('fetches control profile endpoint', async () => {
      mockFetch(PROFILE_RESP)
      await fetchControlProfile(7)
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/greenhouses/7/control-profile/',
      )
    })

    it('fetches control profile with explicit authorization header', async () => {
      mockFetch(PROFILE_RESP)
      await fetchControlProfile(7, { authorization: 'Bearer jwt-token' })
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/greenhouses/7/control-profile/',
        {
          headers: { Authorization: 'Bearer jwt-token' },
        },
      )
    })

    it('PATCHes whitelisted control profile fields', async () => {
      mockFetch(PROFILE_RESP)
      await patchControlProfile(7, { target_low: 54, actuator_enabled: true })
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/greenhouses/7/control-profile/',
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target_low: 54, actuator_enabled: true }),
        },
      )
    })

    it('PATCHes CSRF header and credentials when provided', async () => {
      mockFetch(PROFILE_RESP)
      await patchControlProfile(
        7,
        { target_low: 54 },
        { csrfToken: 'csrf-123', credentials: 'include' },
      )
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/greenhouses/7/control-profile/',
        {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': 'csrf-123',
          },
          body: JSON.stringify({ target_low: 54 }),
          credentials: 'include',
        },
      )
    })
  })
})
