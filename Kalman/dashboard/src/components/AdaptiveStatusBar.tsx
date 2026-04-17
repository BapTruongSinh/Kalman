/**
 * AdaptiveStatusBar summarises adaptive-estimator statuses from the
 * current time-series data.  Statuses: R_updated | R_skipped | skipped.
 */

import type { CyclePoint } from '../api/types'

interface Props {
  data: CyclePoint[]
}

const STATUS_STYLE: Record<string, { bg: string; label: string }> = {
  R_updated: { bg: 'bg-emerald-600', label: 'R updated' },
  R_skipped: { bg: 'bg-yellow-600', label: 'R skipped' },
  skipped: { bg: 'bg-slate-600', label: 'Skipped' },
}

export function AdaptiveStatusBar({ data }: Props) {
  if (data.length === 0) return null

  const counts: Record<string, number> = {}
  for (const pt of data) {
    counts[pt.adaptive_status] = (counts[pt.adaptive_status] ?? 0) + 1
  }

  const total = data.length

  return (
    <section aria-label="Adaptive estimator status breakdown">
      <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
        Adaptive estimator status
      </h3>
      <div className="flex gap-3 flex-wrap">
        {Object.entries(counts).map(([status, count]) => {
          const style = STATUS_STYLE[status] ?? {
            bg: 'bg-slate-700',
            label: status,
          }
          const pct = ((count / total) * 100).toFixed(1)
          return (
            <div
              key={status}
              className={`${style.bg} rounded px-3 py-1.5 text-sm text-white flex items-center gap-2`}
            >
              <span className="font-semibold">{style.label}</span>
              <span className="text-white/70">
                {count.toLocaleString()} ({pct}%)
              </span>
            </div>
          )
        })}
      </div>
    </section>
  )
}
