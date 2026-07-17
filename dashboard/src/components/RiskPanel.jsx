import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { SectionCard, StatCard, StatGrid, Empty, ChartTooltip } from './ui'

export default function RiskPanel({ risk }) {
  if (!risk.length) {
    return (
      <SectionCard title="Study 2: Today's Risk Timeline" accent="rose">
        <Empty>
          Risk timeline is empty. <code className="rounded bg-white/10 px-1.5 py-0.5">ML/Study2/predict.py</code> runs daily via CI. Check back after the next run.
        </Empty>
      </SectionCard>
    )
  }

  const latestDate = risk[risk.length - 1].date
  const dayRows = risk.filter((r) => r.date === latestDate).sort((a, b) => a.time.localeCompare(b.time))

  const violProbs = dayRows.map((r) => r.violation_prob).filter((v) => v !== null)
  const rampProbs = dayRows.map((r) => r.ramp_prob).filter((v) => v !== null)
  const peakViol = dayRows.find((r) => r.violation_prob === Math.max(...violProbs))
  const peakRamp = dayRows.find((r) => r.ramp_prob === Math.max(...rampProbs))

  const chartData = dayRows.map((r) => ({
    time: r.time,
    'Violation risk': r.violation_prob !== null ? r.violation_prob * 100 : null,
    'Ramp-shock risk': r.ramp_prob !== null ? r.ramp_prob * 100 : null,
  }))

  return (
    <SectionCard
      title="Study 2: Today's Risk Timeline"
      subtitle="96-slot (15-min) frequency-violation and ramp-shock risk for the latest complete day. Weak-but-real signal for violation risk, strong for ramp-shock. See ROADMAP.md for honest, out-of-sample PR-AUC numbers."
      accent="rose"
    >
      <StatGrid>
        <StatCard value={dayRows.length} label="Slots covered" sub={latestDate} />
        <StatCard
          value={violProbs.length ? (Math.max(...violProbs) * 100).toFixed(1) + '%' : 'N/A'}
          label="Peak violation risk"
          sub={peakViol ? `at ${peakViol.time}` : null}
          tone="critical"
        />
        <StatCard
          value={rampProbs.length ? (Math.max(...rampProbs) * 100).toFixed(1) + '%' : 'N/A'}
          label="Peak ramp-shock risk"
          sub={peakRamp ? `at ${peakRamp.time}` : null}
          tone="warning"
        />
        <StatCard
          value={violProbs.length ? ((violProbs.reduce((a, b) => a + b, 0) / violProbs.length) * 100).toFixed(2) + '%' : 'N/A'}
          label="Avg. violation risk, today"
        />
      </StatGrid>

      <div className="mt-5 h-72 rounded-2xl border border-white/8 bg-black/20 p-4">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="violGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#fb7185" stopOpacity={0.4} />
                <stop offset="100%" stopColor="#fb7185" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="rampGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.4} />
                <stop offset="100%" stopColor="#38bdf8" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
            <XAxis
              dataKey="time"
              stroke="rgba(255,255,255,0.3)"
              tick={{ fill: '#64748b', fontSize: 11 }}
              interval={11}
            />
            <YAxis stroke="rgba(255,255,255,0.3)" tick={{ fill: '#64748b', fontSize: 11 }} tickFormatter={(v) => v + '%'} width={40} />
            <Tooltip content={<ChartTooltip formatter={(v) => v.toFixed(1) + '%'} />} />
            <Legend wrapperStyle={{ fontSize: 12, color: '#94a3b8' }} />
            <Area type="monotone" dataKey="Violation risk" stroke="#fb7185" strokeWidth={2} fill="url(#violGrad)" />
            <Area type="monotone" dataKey="Ramp-shock risk" stroke="#38bdf8" strokeWidth={2} fill="url(#rampGrad)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </SectionCard>
  )
}
