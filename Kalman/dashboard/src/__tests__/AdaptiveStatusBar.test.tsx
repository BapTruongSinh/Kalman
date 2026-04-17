import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AdaptiveStatusBar } from '../components/AdaptiveStatusBar'
import type { CyclePoint } from '../api/types'

function makePoint(adaptive_status: string, idx = 0): CyclePoint {
  return {
    cycle_index: idx,
    slice_type: 'test',
    sample_ts: null,
    raw_soil_moisture: 50,
    arx_predicted: 50,
    kf_x_posterior: 50,
    kf_innovation: 0,
    kf_R: 1,
    latency_ms: 0.5,
    preprocess_status: 'valid',
    cycle_status: 'ok',
    adaptive_status,
  }
}

describe('AdaptiveStatusBar', () => {
  it('renders nothing when data is empty', () => {
    const { container } = render(<AdaptiveStatusBar data={[]} />)
    expect(container.firstChild).toBeNull()
  })

  it('shows R updated count', () => {
    const data = [
      makePoint('R_updated', 0),
      makePoint('R_updated', 1),
      makePoint('R_skipped', 2),
    ]
    render(<AdaptiveStatusBar data={data} />)
    expect(screen.getByText(/R updated/)).toBeInTheDocument()
    expect(screen.getByText(/2 \(66\.7%\)/)).toBeInTheDocument()
  })

  it('shows R skipped', () => {
    const data = [makePoint('R_skipped', 0)]
    render(<AdaptiveStatusBar data={data} />)
    expect(screen.getByText(/R skipped/)).toBeInTheDocument()
  })

  it('shows skipped status', () => {
    const data = [makePoint('skipped', 0)]
    render(<AdaptiveStatusBar data={data} />)
    expect(screen.getByText(/Skipped/)).toBeInTheDocument()
  })

  it('handles unknown adaptive_status gracefully', () => {
    const data = [makePoint('unknown_status', 0)]
    render(<AdaptiveStatusBar data={data} />)
    expect(screen.getByText(/unknown_status/)).toBeInTheDocument()
  })

  it('has accessible section label', () => {
    const data = [makePoint('R_updated', 0)]
    render(<AdaptiveStatusBar data={data} />)
    expect(
      screen.getByRole('region', {
        name: /adaptive estimator status/i,
      }),
    ).toBeInTheDocument()
  })
})
