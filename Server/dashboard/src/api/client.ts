import type {
  AMPCRecommendation,
  ApiEnvelope,
  ControlProfile,
  MetricsResponse,
  RunSummary,
  SeriesResponse,
} from './types'

const BASE = '/api'

export interface ApiRequestOptions {
  authToken?: string
  authorization?: string
  csrfToken?: string
  credentials?: RequestCredentials
}

function buildHeaders(
  options: ApiRequestOptions = {},
  includeJson = false,
): Record<string, string> {
  const headers: Record<string, string> = {}
  if (includeJson) {
    headers['Content-Type'] = 'application/json'
  }
  if (options.authorization) {
    headers.Authorization = options.authorization
  } else if (options.authToken) {
    headers.Authorization = `Token ${options.authToken}`
  }
  if (options.csrfToken) {
    headers['X-CSRFToken'] = options.csrfToken
  }
  return headers
}

function buildRequestInit(
  options: ApiRequestOptions = {},
  includeJson = false,
): RequestInit | undefined {
  const headers = buildHeaders(options, includeJson)
  const init: RequestInit = {}
  if (Object.keys(headers).length > 0) {
    init.headers = headers
  }
  if (options.credentials) {
    init.credentials = options.credentials
  }
  return Object.keys(init).length > 0 ? init : undefined
}

async function get<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const init = buildRequestInit(options)
  const res = init
    ? await fetch(`${BASE}${path}`, init)
    : await fetch(`${BASE}${path}`)
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} for ${path}`)
  }
  return res.json() as Promise<T>
}

async function requestJson<T>(
  method: 'POST' | 'PATCH',
  path: string,
  body: Record<string, unknown> = {},
  options: ApiRequestOptions = {},
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: buildHeaders(options, true),
    body: JSON.stringify(body),
    ...(options.credentials ? { credentials: options.credentials } : {}),
  })
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} for ${path}`)
  }
  return res.json() as Promise<T>
}

export function fetchRuns(
  options: ApiRequestOptions = {},
): Promise<RunSummary[]> {
  return get<RunSummary[]>('/runs/', options)
}

export interface SeriesParams {
  slice?: string
  limit?: number
  stride?: number
}

export function fetchSeries(
  runId: number,
  params: SeriesParams = {},
  options: ApiRequestOptions = {},
): Promise<SeriesResponse> {
  const qs = new URLSearchParams()
  if (params.slice) qs.set('slice', params.slice)
  if (params.limit != null) qs.set('limit', String(params.limit))
  if (params.stride != null) qs.set('stride', String(params.stride))
  const query = qs.toString() ? `?${qs.toString()}` : ''
  return get<SeriesResponse>(`/runs/${runId}/series/${query}`, options)
}

export function fetchMetrics(
  runId: number,
  options: ApiRequestOptions = {},
): Promise<MetricsResponse> {
  return get<MetricsResponse>(`/runs/${runId}/metrics/`, options)
}

export function runAMPCRecommendation(
  greenhouseId: number,
  options: ApiRequestOptions = {},
): Promise<ApiEnvelope<AMPCRecommendation>> {
  return requestJson<ApiEnvelope<AMPCRecommendation>>(
    'POST',
    `/greenhouses/${greenhouseId}/ampc/recommendations/`,
    {},
    options,
  )
}

export function fetchLatestAMPCRecommendation(
  greenhouseId: number,
  options: ApiRequestOptions = {},
): Promise<ApiEnvelope<AMPCRecommendation>> {
  return get<ApiEnvelope<AMPCRecommendation>>(
    `/greenhouses/${greenhouseId}/ampc/recommendations/latest/`,
    options,
  )
}

export function fetchControlProfile(
  greenhouseId: number,
  options: ApiRequestOptions = {},
): Promise<ApiEnvelope<ControlProfile>> {
  return get<ApiEnvelope<ControlProfile>>(
    `/greenhouses/${greenhouseId}/control-profile/`,
    options,
  )
}

export function patchControlProfile(
  greenhouseId: number,
  body: Partial<
    Pick<
      ControlProfile,
      | 'crop_name'
      | 'crop_kc'
      | 'target_low'
      | 'target_high'
      | 'pump_max_seconds'
      | 'soft_daily_pump_cap_seconds'
      | 'actuator_enabled'
    >
  >,
  options: ApiRequestOptions = {},
): Promise<ApiEnvelope<ControlProfile>> {
  return requestJson<ApiEnvelope<ControlProfile>>(
    'PATCH',
    `/greenhouses/${greenhouseId}/control-profile/`,
    body,
    options,
  )
}
