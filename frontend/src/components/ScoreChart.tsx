import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ExperimentEntry } from '../types/events'

export function ScoreChart({
  experiments,
  targetScore,
  metric = 'f1',
}: {
  experiments: ExperimentEntry[]
  targetScore: number
  metric?: string
}) {
  const data = experiments.map((e, i) => {
    const f1 = e.validationMetrics[metric]
    return {
      index: i + 1,
      id: e.experimentId,
      family: e.modelFamily ?? e.experimentId,
      status: e.status,
      f1: typeof f1 === 'number' ? f1 : null,
      note: e.note,
    }
  })
  const scored = data.filter((d) => typeof d.f1 === 'number').length

  return (
    <section>
      <h2 className="font-display text-xl text-paper">Validation {metric.toUpperCase()} by experiment</h2>
      <p className="mb-3 text-sm text-mist">
        {metric === 'mae' ? 'Lower is better · chronological validation' : `Positive class · target ${targetScore.toFixed(2)}`}
        {experiments.length > 0
          ? ` · ${scored} scored / ${experiments.length} trials`
          : ''}
      </p>
      <div className="h-48 w-full">
        {data.length === 0 ? (
          <div className="flex h-full items-center justify-center border border-dashed border-line text-sm text-mist">
            No validation scores yet
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="rgba(90,114,103,0.2)" strokeDasharray="3 3" />
              <XAxis dataKey="index" stroke="#5a7267" fontSize={11} />
              <YAxis domain={metric === 'mae' ? [0, 'auto'] : [0, 1]} stroke="#5a7267" fontSize={11} width={32} />
              <Tooltip
                contentStyle={{
                  background: '#ffffff',
                  border: '1px solid #c8d5ce',
                  borderRadius: 0,
                  fontSize: 12,
                  color: '#14241e',
                }}
                formatter={(value, _name, item) => {
                  const row = item?.payload as {
                    f1: number | null
                    status: string
                    family: string
                    note?: string
                  }
                  if (row.f1 == null) {
                    return [row.note || row.status || 'no score', row.family]
                  }
                  return [Number(value).toFixed(3), row.family]
                }}
              />
              {metric !== 'mae' && <ReferenceLine
                y={targetScore}
                stroke="#9a6b12"
                strokeDasharray="4 4"
                label={{ value: `Target ${targetScore.toFixed(2)}`, fill: '#9a6b12', fontSize: 11 }}
              />}
              <Line
                type="monotone"
                dataKey="f1"
                stroke="#0d8f6e"
                strokeWidth={2}
                connectNulls={false}
                dot={(props) => {
                  const { cx, cy, payload } = props
                  if (cx == null || cy == null) return null
                  if (payload.f1 == null) {
                    return (
                      <circle
                        key={`miss-${payload.index}`}
                        cx={cx}
                        cy={4}
                        r={3}
                        fill="transparent"
                        stroke="#b42318"
                        strokeWidth={1.5}
                      />
                    )
                  }
                  return (
                    <circle
                      key={`hit-${payload.index}`}
                      cx={cx}
                      cy={cy}
                      r={4}
                      fill="#0d8f6e"
                    />
                  )
                }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  )
}
