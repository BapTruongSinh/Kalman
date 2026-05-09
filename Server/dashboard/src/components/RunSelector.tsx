import { useQuery } from '@tanstack/react-query'
import { fetchRuns } from '../api/client'
import type { RunSummary } from '../api/types'

interface Props {
  selectedId: number | null
  onSelect: (id: number) => void
}

const STATUS_COLOR: Record<string, string> = {
  completed: 'bg-green-500',
  running: 'bg-yellow-400',
  failed: 'bg-red-500',
  pending: 'bg-slate-400',
}

export function RunSelector({ selectedId, onSelect }: Props) {
  const { data, isLoading, isError } = useQuery<RunSummary[]>({
    queryKey: ['runs'],
    queryFn: () => fetchRuns(),
    staleTime: 30_000,
  })

  if (isLoading) {
    return (
      <div className="p-4 text-slate-400" role="status" aria-live="polite">
        Loading runs…
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="p-4 text-red-400" role="alert">
        Failed to load experiment runs.
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className="p-4 text-slate-400">
        No experiment runs found.
      </div>
    )
  }

  return (
    <nav aria-label="Experiment runs">
      <ul className="space-y-1">
        {data.map((run) => {
          const isSelected = run.id === selectedId
          const dotClass = STATUS_COLOR[run.status] ?? 'bg-slate-400'
          return (
            <li key={run.id}>
              <button
                type="button"
                onClick={() => onSelect(run.id)}
                aria-pressed={isSelected}
                className={[
                  'w-full text-left px-3 py-2 rounded-md text-sm transition-colors',
                  isSelected
                    ? 'bg-blue-700 text-white font-semibold'
                    : 'text-slate-300 hover:bg-slate-700',
                ].join(' ')}
              >
                <span className="flex items-center gap-2">
                  <span
                    className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${dotClass}`}
                    aria-hidden="true"
                  />
                  <span className="truncate">{run.name}</span>
                </span>
                <span className="block text-xs text-slate-400 mt-0.5 pl-4">
                  {run.run_type} · {run.status}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
