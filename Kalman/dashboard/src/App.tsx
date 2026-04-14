import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { RunDashboard } from './components/RunDashboard'
import { RunSelector } from './components/RunSelector'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

function App() {
  const [selectedRun, setSelectedRun] = useState<number | null>(null)

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col">
        {/* Top bar */}
        <header className="border-b border-slate-700 px-6 py-3 flex items-center gap-3">
          <h1 className="text-lg font-bold text-white">
            Kalman Pipeline Dashboard
          </h1>
          <span className="text-xs text-slate-400">
            Raw · Predicted · Filtered
          </span>
        </header>

        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar */}
          <aside
            className="w-64 flex-shrink-0 border-r border-slate-700 overflow-y-auto p-4"
            aria-label="Experiment run list"
          >
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
              Experiment runs
            </h2>
            <RunSelector
              selectedId={selectedRun}
              onSelect={setSelectedRun}
            />
          </aside>

          {/* Main content */}
          <main className="flex-1 overflow-y-auto p-6">
            {selectedRun == null ? (
              <div className="flex flex-col items-center justify-center h-full text-slate-500">
                <p className="text-2xl mb-2">←</p>
                <p>Select an experiment run to view its dashboard.</p>
              </div>
            ) : (
              <RunDashboard runId={selectedRun} />
            )}
          </main>
        </div>
      </div>
    </QueryClientProvider>
  )
}

export default App
