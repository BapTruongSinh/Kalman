/** Lightweight run summary as returned by GET /api/runs/ */
export interface RunSummary {
  id: number
  name: string
  run_type: string
  status: string
  created_at: string
  dataset_source: string | null
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

/** Per-slice evaluation metrics */
export interface SliceMetrics {
  slice_type: string
  n_samples: number
  n_valid: number
  n_skipped: number | null
  n_error: number | null
  rmse_arx: number | null
  rmse_filtered: number | null
  mae_arx: number | null
  mae_filtered: number | null
  variance_reduction: number | null
  pass_variance_reduction: boolean | null
  pass_rmse_guardrail: boolean | null
  pass_mae_guardrail: boolean | null
  cycle_success_rate: number | null
  sample_loss_rate: number | null
  passes_acceptance_gate: boolean | null
}

/** Envelope for GET /api/runs/:id/metrics/ */
export interface MetricsResponse {
  run_id: number
  run_name: string
  slices: Record<string, SliceMetrics>
}
