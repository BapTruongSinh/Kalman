/** Lightweight run summary as returned by GET /api/runs/ */
export interface RunSummary {
  id: number
  name: string
  run_type: string
  status: string
  greenhouse_id: number
  greenhouse_name: string
  created_at: string
}

/** One PipelineCycle row as returned by GET /api/runs/:id/series/ */
export interface CyclePoint {
  greenhouse_id: number
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
  greenhouse_id: number
  greenhouse_name: string
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
  greenhouse_id: number
  greenhouse_name: string
  slices: Record<string, SliceMetrics>
}

export interface ApiEnvelope<T> {
  success: boolean
  data: T | null
  error: {
    code: string
    message: string
    details: unknown
    trace_id: string
  } | null
}

export interface ControlProfile {
  id: number
  greenhouse_id: number
  crop_name: string
  crop_kc: number
  target_low: number
  target_high: number
  pump_max_seconds: number
  soft_daily_pump_cap_seconds: number
  actuator_enabled: boolean
  actuator_configured: boolean
  created_at: string
  updated_at: string
}

export interface AMPCRecommendation {
  id: number
  greenhouse_id: number
  mode: string
  state_cycle_id: number | null
  run_id: number | null
  pump_seconds: number
  step_seconds: number
  predicted_soil_moisture: number[]
  target_band: { low: number; high: number }
  cost: number
  safety_status: string
  reason: string
  bias_correction: number
  bias_window_count: number
  used_today_pump_seconds: number
  actuator: {
    enabled: boolean
    executed: boolean
    status: string
    command: Record<string, unknown> | null
    http_status_code: number | null
    alert: string | null
    error: string | null
  }
  created_at: string
}
