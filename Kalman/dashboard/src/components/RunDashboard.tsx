/**
 * RunDashboard fetches series for one selected run and composes the chart
 * with adaptive status diagnostics.
 */

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { fetchSeries } from '../api/client'
import type { CyclePoint, SeriesResponse } from '../api/types'
import { AdaptiveStatusBar } from './AdaptiveStatusBar'
import { SliceChart } from './SliceChart'

const SLICE_OPTIONS = ['all', 'train', 'validation', 'test'] as const
type SliceOption = (typeof SLICE_OPTIONS)[number]

const STRIDE_OPTIONS = [1, 2, 5, 10] as const

interface Props {
  runId: number
}

function pickSliceFilter(option: SliceOption): string | undefined {
  return option === 'all' ? undefined : option
}

function filterBySlice(data: CyclePoint[], slice: SliceOption): CyclePoint[] {
  if (slice === 'all') return data
  return data.filter((d) => d.slice_type === slice)
}

export function RunDashboard({ runId }: Props) {
  // Default to train: backend "all" without slice is capped by limit and skews
  // toward low cycle_index (mostly train in chronological splits).
  const [slice, setSlice] = useState<SliceOption>('train')
  const [stride, setStride] = useState<number>(1)

  const seriesKey = ['series', runId, slice, stride]
  const {
    data: series,
    isLoading: seriesLoading,
    isError: seriesError,
    dataUpdatedAt,
  } = useQuery<SeriesResponse>({
    queryKey: seriesKey,
    queryFn: () =>
      fetchSeries(runId, {
        slice: pickSliceFilter(slice),
        stride,
        limit: 4000,
      }),
    staleTime: 60_000,
  })

  const chartData = series ? filterBySlice(series.data, slice) : []

  // Group chart data by slice for multi-slice "all" view
  const sliceGroups: Record<string, CyclePoint[]> =
    slice === 'all'
      ? chartData.reduce(
          (acc, pt) => {
            acc[pt.slice_type] = acc[pt.slice_type] ?? []
            acc[pt.slice_type].push(pt)
            return acc
          },
          {} as Record<string, CyclePoint[]>,
        )
      : { [slice]: chartData }

  const lastUpdated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString()
    : null

  return (
    <div className="space-y-6">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-4">
        {/* Slice filter */}
        <fieldset>
          <legend className="sr-only">Slice filter</legend>
          <div className="flex gap-1" role="group" aria-label="Slice filter">
            {SLICE_OPTIONS.map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => setSlice(opt)}
                aria-pressed={slice === opt}
                className={[
                  'px-3 py-1 rounded text-sm capitalize transition-colors',
                  slice === opt
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600',
                ].join(' ')}
              >
                {opt}
              </button>
            ))}
          </div>
        </fieldset>

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
      {!seriesLoading &&
        Object.entries(sliceGroups).map(([sliceKey, pts]) => (
          <div key={sliceKey} className="bg-slate-800 rounded-lg p-4 space-y-4">
            <SliceChart data={pts} sliceLabel={sliceKey} />
            <AdaptiveStatusBar data={pts} />
          </div>
        ))}
    </div>
  )
}
