/**
 * MetricsPanel shows online evaluation metrics for a single run.
 * Each metric row colour-codes pass/fail with an explicit text label
 * so it is accessible without relying on colour alone.
 */

import type { MetricsResponse, SliceMetrics } from '../api/types'

interface Props {
  metrics: MetricsResponse
}

function pct(v: number | null): string {
  if (v == null) return '—'
  return `${(v * 100).toFixed(1)}%`
}

function num(v: number | null, decimals = 4): string {
  if (v == null) return '—'
  return v.toFixed(decimals)
}

function Gate({ pass }: { pass: boolean | null }) {
  if (pass === null) {
    return (
      <span className="text-slate-500" aria-label="N/A">
        N/A
      </span>
    )
  }
  return (
    <span
      className={pass ? 'text-emerald-400' : 'text-red-400'}
      aria-label={pass ? 'Pass' : 'Fail'}
    >
      {pass ? 'Pass' : 'Fail'}
    </span>
  )
}

function SliceTable({ s }: { s: SliceMetrics }) {
  const rows: Array<{ label: string; value: React.ReactNode }> = [
    { label: 'n_samples', value: s.n_samples },
    { label: 'n_valid', value: s.n_valid },
    { label: 'Cycle success rate', value: pct(s.cycle_success_rate) },
    { label: 'Sample loss rate', value: pct(s.sample_loss_rate) },
    { label: 'RMSE (ARX)', value: num(s.rmse_arx) },
    { label: 'RMSE (filtered)', value: num(s.rmse_filtered) },
    { label: 'MAE (ARX)', value: num(s.mae_arx) },
    { label: 'MAE (filtered)', value: num(s.mae_filtered) },
    { label: 'Variance reduction', value: num(s.variance_reduction, 4) },
    {
      label: 'Variance reduction gate',
      value: <Gate pass={s.pass_variance_reduction} />,
    },
    {
      label: 'RMSE guardrail',
      value: <Gate pass={s.pass_rmse_guardrail} />,
    },
    {
      label: 'MAE guardrail',
      value: <Gate pass={s.pass_mae_guardrail} />,
    },
    {
      label: 'Acceptance gate',
      value:
        s.passes_acceptance_gate === null ? (
          <span className="text-slate-500 font-bold" aria-label="N/A">N/A</span>
        ) : (
          <span
            className={
              s.passes_acceptance_gate
                ? 'text-emerald-300 font-bold'
                : 'text-red-300 font-bold'
            }
          >
            {s.passes_acceptance_gate ? 'PASS' : 'FAIL'}
          </span>
        ),
    },
  ]

  return (
    <table
      className="w-full text-sm border-collapse"
      aria-label={`Metrics for ${s.slice_type} slice`}
    >
      <thead>
        <tr>
          <th className="text-left py-1 pr-4 text-slate-400 font-normal w-1/2">
            Metric
          </th>
          <th className="text-right py-1 text-slate-400 font-normal">Value</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.label} className="border-t border-slate-700">
            <td className="py-1 pr-4 text-slate-300">{row.label}</td>
            <td className="py-1 text-right font-mono text-slate-200">
              {row.value}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

const SLICE_ORDER = ['online'] as const

export function MetricsPanel({ metrics }: Props) {
  const sliceEntries = SLICE_ORDER.filter((s) => metrics.slices[s]).map(
    (s) => metrics.slices[s],
  )

  // Also include any slice not in the canonical order
  Object.keys(metrics.slices).forEach((k) => {
    if (!SLICE_ORDER.includes(k as typeof SLICE_ORDER[number])) {
      sliceEntries.push(metrics.slices[k])
    }
  })

  if (sliceEntries.length === 0) {
    return (
      <p className="text-slate-500 text-sm p-4">
        No evaluation metrics available for this run.
      </p>
    )
  }

  return (
    <div className="grid gap-4 md:grid-cols-3">
      {sliceEntries.map((s) => (
        <section
          key={s.slice_type}
          className="bg-slate-800 rounded-lg p-4"
          aria-label={`${s.slice_type} slice metrics`}
        >
          <h3 className="font-semibold text-slate-200 mb-3 capitalize">
            {s.slice_type}
          </h3>
          <SliceTable s={s} />
        </section>
      ))}
    </div>
  )
}
