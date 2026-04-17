import type { MetricsResponse, RunSummary, SeriesResponse } from './types'

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} for ${path}`)
  }
  return res.json() as Promise<T>
}

export function fetchRuns(): Promise<RunSummary[]> {
  return get<RunSummary[]>('/runs/')
}

export interface SeriesParams {
  slice?: string
  limit?: number
  stride?: number
}

export function fetchSeries(
  runId: number,
  params: SeriesParams = {},
): Promise<SeriesResponse> {
  const qs = new URLSearchParams()
  if (params.slice) qs.set('slice', params.slice)
  if (params.limit != null) qs.set('limit', String(params.limit))
  if (params.stride != null) qs.set('stride', String(params.stride))
  const query = qs.toString() ? `?${qs.toString()}` : ''
  return get<SeriesResponse>(`/runs/${runId}/series/${query}`)
}

export function fetchMetrics(runId: number): Promise<MetricsResponse> {
  return get<MetricsResponse>(`/runs/${runId}/metrics/`)
}
