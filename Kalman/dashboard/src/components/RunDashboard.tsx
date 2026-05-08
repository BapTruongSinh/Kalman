/**
 * RunDashboard fetches series and metrics for one selected run and
 * composes the SliceChart, AdaptiveStatusBar, and MetricsPanel.
 */

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { fetchMetrics, fetchSeries } from '../api/client'
import type { SeriesResponse, MetricsResponse } from '../api/types'
import { AdaptiveStatusBar } from './AdaptiveStatusBar'
import { MetricsPanel } from './MetricsPanel'
import { SliceChart } from './SliceChart'

const STRIDE_OPTIONS = [1, 2, 5, 10] as const
const ONLINE_SLICE = 'online'

interface Props {
  runId: number
}

export function RunDashboard({ runId }: Props) {
  const [stride, setStride] = useState<number>(1)

  const seriesKey = ['series', runId, ONLINE_SLICE, stride]
  const {
    data: series,
    isLoading: seriesLoading,
    isError: seriesError,
    dataUpdatedAt,
  } = useQuery<SeriesResponse>({
    queryKey: seriesKey,
    queryFn: () =>
      fetchSeries(runId, {
        slice: ONLINE_SLICE,
        stride,
        limit: 4000,
      }),
    staleTime: 60_000,
  })

  const { data: metrics, isLoading: metricsLoading } =
    useQuery<MetricsResponse>({
      queryKey: ['metrics', runId],
      queryFn: () => fetchMetrics(runId),
      staleTime: 60_000,
    })

  const chartData = series ? series.data : []

  const lastUpdated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString()
    : null

  return (
    <div className="space-y-6">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-4">
        <span className="px-3 py-1 rounded text-sm bg-blue-600 text-white">
          Online
        </span>

        {/* Stride selector */}
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <span>Stride:</span>
          <select
            value={stride}
            onChange={(e) => setStride(Number(e.target.value))}
            className="bg-slate-700 text-slate-200 rounded px-2 py-1 text-sm"
            aria-label="Stride — sample every Nth cycle"
          >
            {STRIDE_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s === 1 ? 'Every cycle' : `Every ${s}th`}
              </option>
            ))}
          </select>
        </label>

        {/* Status/count */}
        {series && (
          <p className="text-xs text-slate-400 ml-auto" aria-live="polite">
            Showing {series.returned.toLocaleString()} /{' '}
            {series.total_cycles.toLocaleString()} cycles
            {lastUpdated && ` · updated ${lastUpdated}`}
          </p>
        )}
      </div>

      {/* Loading/error states */}
      {seriesLoading && (
        <div className="text-slate-400 text-sm" role="status" aria-live="polite">
          Loading time-series data…
        </div>
      )}
      {seriesError && (
        <div className="text-red-400 text-sm" role="alert">
          Failed to load series data.
        </div>
      )}

      {/* Charts per slice */}
      {!seriesLoading && (
        <div className="bg-slate-800 rounded-lg p-4 space-y-4">
          <SliceChart data={chartData} sliceLabel={ONLINE_SLICE} />
          <AdaptiveStatusBar data={chartData} />
        </div>
      )}

      {/* Metrics */}
      <section aria-label="Evaluation metrics">
        <h2 className="text-base font-semibold text-slate-200 mb-3">
          Evaluation metrics
        </h2>
        {metricsLoading ? (
          <div className="text-slate-400 text-sm" role="status">
            Loading metrics…
          </div>
        ) : metrics ? (
          <MetricsPanel metrics={metrics} />
        ) : null}
      </section>
    </div>
  )
}
