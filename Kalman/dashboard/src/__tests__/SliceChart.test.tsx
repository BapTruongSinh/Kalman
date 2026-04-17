import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SliceChart } from '../components/SliceChart'
import type { CyclePoint } from '../api/types'

function makePoint(idx: number): CyclePoint {
  return {
    cycle_index: idx,
    slice_type: 'test',
    sample_ts: null,
    raw_soil_moisture: 50 + idx * 0.1,
    arx_predicted: 50.1 + idx * 0.1,
    kf_x_posterior: 50.05 + idx * 0.1,
    kf_innovation: 0.1,
    kf_R: 1.0,
    latency_ms: 0.5,
    preprocess_status: 'valid',
    cycle_status: 'ok',
    adaptive_status: 'R_updated',
  }
}

describe('SliceChart', () => {
  it('shows empty state when data is empty', () => {
    render(<SliceChart data={[]} sliceLabel="test" />)
    expect(screen.getByText(/no data for slice/i)).toBeInTheDocument()
  })

  it('renders a section with accessible label', () => {
    const data = [makePoint(0), makePoint(1)]
    render(<SliceChart data={data} sliceLabel="train" />)
    expect(
      screen.getByRole('region', { name: /time-series chart for train/i }),
    ).toBeInTheDocument()
  })

  it('shows cycle count in heading', () => {
    const data = Array.from({ length: 5 }, (_, i) => makePoint(i))
    render(<SliceChart data={data} sliceLabel="validation" />)
    expect(screen.getByText(/5 cycles/)).toBeInTheDocument()
  })

  it('renders chart with SVG', () => {
    const data = [makePoint(0)]
    const { container } = render(<SliceChart data={data} sliceLabel="test" />)
    expect(container.querySelector('svg')).not.toBeNull()
  })
})
