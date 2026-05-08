/**
 * SliceChart renders three time-series on one Recharts chart:
 *   – Raw sensor  (solid line + circle dot)
 *   – ARX predicted (dashed line + square dot)
 *   – KF filtered   (dot-dash line + triangle dot)
 *
 * Line patterns and dot shapes differ so the chart is readable in
 * greyscale or by users with colour-vision deficiency (WCAG 1.4.1).
 */

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { CyclePoint } from '../api/types'

interface Props {
  data: CyclePoint[]
  /** e.g. "online" */
  sliceLabel: string
}

const COLORS = {
  raw: '#60a5fa',       // blue-400
  predicted: '#f59e0b', // amber-400
  filtered: '#34d399',  // emerald-400
}

function formatIndex(value: number) {
  return `#${value}`
}

function formatValue(value: number | null) {
  if (value == null) return 'N/A'
  return value.toFixed(3)
}

/** Custom tooltip renders all three series values */
function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: Array<{ name: string; value: number | null; color: string }>
  label?: number
}) {
  if (!active || !payload?.length) return null
  return (
    <div
      className="bg-slate-900 border border-slate-600 rounded p-2 text-xs shadow-lg"
      role="tooltip"
    >
      <p className="font-semibold text-slate-200 mb-1">Cycle {label}</p>
      {payload.map((entry) => (
        <p key={entry.name} style={{ color: entry.color }}>
          {entry.name}: {formatValue(entry.value)}
        </p>
      ))}
    </div>
  )
}

/** Triangle svg shape for the KF-filtered series */
function TriangleDot(props: {
  cx?: number
  cy?: number
  fill?: string
}) {
  const { cx = 0, cy = 0, fill } = props
  const size = 4
  return (
    <polygon
      points={`${cx},${cy - size} ${cx - size},${cy + size} ${cx + size},${cy + size}`}
      fill={fill}
    />
  )
}

/** Square svg shape for ARX-predicted series */
function SquareDot(props: { cx?: number; cy?: number; fill?: string }) {
  const { cx = 0, cy = 0, fill } = props
  const half = 3
  return (
    <rect
      x={cx - half}
      y={cy - half}
      width={half * 2}
      height={half * 2}
      fill={fill}
    />
  )
}

export function SliceChart({ data, sliceLabel }: Props) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-slate-500">
        No data for slice "{sliceLabel}"
      </div>
    )
  }

  return (
    <section aria-label={`Time-series chart for ${sliceLabel} slice`}>
      <h3 className="text-sm font-semibold text-slate-300 mb-2 capitalize">
        {sliceLabel} slice — {data.length.toLocaleString()} cycles
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart
          data={data}
          margin={{ top: 4, right: 16, bottom: 4, left: 4 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            dataKey="cycle_index"
            tickFormatter={formatIndex}
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            label={{
              value: 'Cycle index',
              position: 'insideBottomRight',
              offset: -4,
              fill: '#64748b',
              fontSize: 11,
            }}
          />
          <YAxis
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            label={{
              value: 'Soil moisture (%)',
              angle: -90,
              position: 'insideLeft',
              fill: '#64748b',
              fontSize: 11,
            }}
            width={60}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ fontSize: 12, color: '#cbd5e1' }}
            formatter={(value) => (
              <span style={{ color: '#cbd5e1' }}>{value}</span>
            )}
          />

          {/* Raw sensor — solid line, circle dot */}
          <Line
            type="monotone"
            dataKey="raw_soil_moisture"
            name="Raw sensor"
            stroke={COLORS.raw}
            strokeWidth={1.5}
            dot={false}
            activeDot={{ r: 4 }}
            connectNulls
          />

          {/* ARX predicted — dashed line, square dot */}
          <Line
            type="monotone"
            dataKey="arx_predicted"
            name="ARX predicted"
            stroke={COLORS.predicted}
            strokeWidth={1.5}
            strokeDasharray="6 3"
            dot={<SquareDot fill={COLORS.predicted} />}
            activeDot={{ r: 4 }}
            connectNulls
          />

          {/* KF filtered — dot-dash line, triangle dot */}
          <Line
            type="monotone"
            dataKey="kf_x_posterior"
            name="KF filtered"
            stroke={COLORS.filtered}
            strokeWidth={1.5}
            strokeDasharray="2 4"
            dot={<TriangleDot fill={COLORS.filtered} />}
            activeDot={{ r: 4 }}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </section>
  )
}
