import type { ExperimentEntry } from '../types/events'

export function BestVsPrevious({ experiments, metric = 'f1' }: { experiments: ExperimentEntry[]; metric?: string }) {
  const scored = experiments
    .filter((e) => typeof e.validationMetrics[metric] === 'number')
    .map((e) => ({ e, f1: e.validationMetrics[metric] as number }))

  if (scored.length === 0) {
    return (
      <section>
        <h2 className="font-display text-xl text-paper">Best versus previous model</h2>
        <p className="mt-2 text-sm text-mist">Waiting for completed trials…</p>
      </section>
    )
  }

  const best = scored.reduce((a, b) => ((metric === 'mae' ? b.f1 < a.f1 : b.f1 > a.f1) ? b : a))
  const previous =
    scored.length > 1
      ? scored.filter((s) => s.e.experimentId !== best.e.experimentId).at(-1)
      : undefined

  return (
    <section>
      <h2 className="font-display text-xl text-paper">Best versus previous model</h2>
      <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
        <CompareCol title={`Best · ${best.e.experimentId}`} entry={best.e} metric={metric} highlight />
        <CompareCol
          title={previous ? `Previous · ${previous.e.experimentId}` : 'Previous'}
          entry={previous?.e}
          metric={metric}
        />
      </div>
    </section>
  )
}

function CompareCol({
  title,
  entry,
  highlight,
  metric,
}: {
  title: string
  entry?: ExperimentEntry
  highlight?: boolean
  metric: string
}) {
  return (
    <div className={`border border-line p-3 ${highlight ? 'border-teal/50 bg-teal/5' : 'bg-panel/40'}`}>
      <p className="font-mono text-[11px] uppercase tracking-wide text-mist">{title}</p>
      {entry ? (
        <ul className="mt-2 space-y-1 font-mono text-xs">
          <li>
            Val {metric.toUpperCase()} <span className="text-paper">{fmt(entry.validationMetrics[metric])}</span>
          </li>
          <li>
            {metric === 'mae' ? 'RMSE' : 'Precision'} <span className="text-paper">{fmt(entry.validationMetrics[metric === 'mae' ? 'rmse' : 'precision'])}</span>
          </li>
          <li>
            {metric === 'mae' ? 'R²' : 'Recall'} <span className="text-paper">{fmt(entry.validationMetrics[metric === 'mae' ? 'r2' : 'recall'])}</span>
          </li>
        </ul>
      ) : (
        <p className="mt-2 text-xs text-mist">—</p>
      )}
    </div>
  )
}

function fmt(n?: number) {
  return typeof n === 'number' ? n.toFixed(2) : '—'
}
