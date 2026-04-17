/** Lightweight run summary as returned by GET /api/runs/ */
export interface RunSummary {
  id: number
  name: string
  run_type: string
  status: string
  created_at: string
}

/** One PipelineCycle row as returned by GET /api/runs/:id/series/ */
export interface CyclePoint {
  cycle_index: number
  slice_type: string
  sample_ts: string | null
  raw_soil_moisture: number | null
  arx_predicted: number | null
  kf_x_posterior: number | null
  kf_innovation: number | null
  kf_R: number | null
  latency_ms: number | null
  preprocess_status: string
  cycle_status: string
  /** "R_updated" | "R_skipped" | "skipped" */
  adaptive_status: string
}

/** Envelope for GET /api/runs/:id/series/ */
export interface SeriesResponse {
  run_id: number
  run_name: string
  run_status: string
  total_cycles: number
  returned: number
  data: CyclePoint[]
}

