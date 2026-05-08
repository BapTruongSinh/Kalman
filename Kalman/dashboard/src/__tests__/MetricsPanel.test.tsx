import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MetricsPanel } from '../components/MetricsPanel'
import type { MetricsResponse, SliceMetrics } from '../api/types'

function makeSlice(overrides: Partial<SliceMetrics> = {}): SliceMetrics {
  return {
    slice_type: 'online',
    n_samples: 100,
    n_valid: 95,
    n_skipped: 3,
    n_error: 2,
    rmse_arx: 0.42,
    rmse_filtered: 0.38,
    mae_arx: 0.35,
    mae_filtered: 0.30,
    variance_reduction: 0.25,
    pass_variance_reduction: true as boolean | null,
    pass_rmse_guardrail: true as boolean | null,
    pass_mae_guardrail: true as boolean | null,
    cycle_success_rate: 0.95,
    sample_loss_rate: 0.05,
    passes_acceptance_gate: true as boolean | null,
    ...overrides,
  }
}

function makeMetrics(slices: Record<string, SliceMetrics>): MetricsResponse {
  return {
    run_id: 1,
    run_name: 'live-run',
    slices,
  }
}

describe('MetricsPanel', () => {
  it('shows "no metrics" message when slices is empty', () => {
    render(<MetricsPanel metrics={makeMetrics({})} />)
    expect(screen.getByText(/no evaluation metrics/i)).toBeInTheDocument()
  })

  it('renders the online slice', () => {
    render(<MetricsPanel metrics={makeMetrics({ online: makeSlice() })} />)
    expect(screen.getByRole('region', { name: /online slice/i })).toBeInTheDocument()
  })

  it('shows PASS for acceptance gate when all gates pass', () => {
    render(<MetricsPanel metrics={makeMetrics({ online: makeSlice() })} />)
    expect(screen.getByText(/^PASS$/)).toBeInTheDocument()
  })

  it('shows FAIL for acceptance gate when variance reduction fails', () => {
    const s = makeSlice({ pass_variance_reduction: false, passes_acceptance_gate: false })
    render(<MetricsPanel metrics={makeMetrics({ online: s })} />)
    expect(screen.getByText(/^FAIL$/)).toBeInTheDocument()
  })

  it('shows null metrics as em-dash', () => {
    const s = makeSlice({ rmse_arx: null, mae_arx: null })
    render(<MetricsPanel metrics={makeMetrics({ online: s })} />)
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBeGreaterThan(0)
  })

  it('renders cycle success rate as percentage', () => {
    render(<MetricsPanel metrics={makeMetrics({ online: makeSlice({ cycle_success_rate: 0.95 }) })} />)
    expect(screen.getByText('95.0%')).toBeInTheDocument()
  })

  it('shows N/A for null gate flags instead of Fail', () => {
    const s = makeSlice({
      pass_variance_reduction: null,
      pass_rmse_guardrail: null,
      pass_mae_guardrail: null,
      passes_acceptance_gate: null,
    })
    render(<MetricsPanel metrics={makeMetrics({ online: s })} />)
    const nas = screen.getAllByText('N/A')
    expect(nas.length).toBeGreaterThanOrEqual(4)
    expect(screen.queryByText(/^Fail$/)).toBeNull()
    expect(screen.queryByText(/^FAIL$/)).toBeNull()
  })

  it('renders online slice before unknown legacy keys', () => {
    const m = makeMetrics({
      legacy: makeSlice({ slice_type: 'legacy' }),
      online: makeSlice({ slice_type: 'online' }),
    })
    render(<MetricsPanel metrics={m} />)
    const headers = screen.getAllByRole('heading', { level: 3 })
    const names = headers.map((h) => h.textContent?.toLowerCase())
    expect(names[0]).toContain('online')
    expect(names[1]).toContain('legacy')
  })
})
