import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { RunSelector } from '../components/RunSelector'
import * as client from '../api/client'
import type { RunSummary } from '../api/types'

const RUNS: RunSummary[] = [
  {
    id: 1,
    name: 'run-alpha',
    run_type: 'live',
    status: 'completed',
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 2,
    name: 'run-beta',
    run_type: 'live',
    status: 'failed',
    created_at: '2024-01-02T00:00:00Z',
  },
]

function wrapper(children: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('RunSelector', () => {
  beforeEach(() => {
    vi.spyOn(client, 'fetchRuns').mockResolvedValue(RUNS)
  })

  it('shows loading state initially', async () => {
    render(wrapper(<RunSelector selectedId={null} onSelect={() => {}} />))
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('renders run names after load', async () => {
    render(wrapper(<RunSelector selectedId={null} onSelect={() => {}} />))
    expect(await screen.findByText('run-alpha')).toBeInTheDocument()
    expect(screen.getByText('run-beta')).toBeInTheDocument()
  })

  it('marks selected run as pressed', async () => {
    render(wrapper(<RunSelector selectedId={1} onSelect={() => {}} />))
    const btn = await screen.findByRole('button', { name: /run-alpha/i })
    expect(btn).toHaveAttribute('aria-pressed', 'true')
  })

  it('calls onSelect with run id when clicked', async () => {
    const onSelect = vi.fn()
    render(wrapper(<RunSelector selectedId={null} onSelect={onSelect} />))
    const btn = await screen.findByRole('button', { name: /run-beta/i })
    await userEvent.click(btn)
    expect(onSelect).toHaveBeenCalledWith(2)
  })

  it('shows error message when fetch fails', async () => {
    vi.spyOn(client, 'fetchRuns').mockRejectedValue(new Error('network error'))
    render(wrapper(<RunSelector selectedId={null} onSelect={() => {}} />))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })

  it('shows empty state when no runs', async () => {
    vi.spyOn(client, 'fetchRuns').mockResolvedValue([])
    render(wrapper(<RunSelector selectedId={null} onSelect={() => {}} />))
    expect(await screen.findByText(/no experiment runs/i)).toBeInTheDocument()
  })
})
