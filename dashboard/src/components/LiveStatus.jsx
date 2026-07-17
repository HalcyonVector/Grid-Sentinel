import { SectionCard, StatCard, StatGrid, Empty } from './ui'
import { fmtMW, fmtPct } from '../lib/format'

const GEN_MIX = [
  { name: 'Coal', key: 'gen_coal_mu', color: '#64748b' },
  { name: 'Hydro', key: 'gen_hydro_mu', color: '#38bdf8' },
  { name: 'RES (wind/solar)', key: 'gen_res_mu', color: '#fbbf24' },
  { name: 'Nuclear', key: 'gen_nuclear_mu', color: '#a78bfa' },
  { name: 'Gas', key: 'gen_gas_mu', color: '#fb7185' },
  { name: 'Lignite', key: 'gen_lignite_mu', color: '#94a3b8' },
]

export default function LiveStatus({ dailySlim }) {
  if (!dailySlim.length) {
    return (
      <SectionCard title="Live Grid Status" subtitle="Latest published NLDC daily figures.">
        <Empty>No data available.</Empty>
      </SectionCard>
    )
  }

  const latest = dailySlim[dailySlim.length - 1]
  const prev = dailySlim.length > 1 ? dailySlim[dailySlim.length - 2] : null

  const demand = latest.max_demand_met_total_mw
  const demandDelta = prev ? demand - prev.max_demand_met_total_mw : null
  const res = latest.share_res_pct
  const freqBelow = latest.freq_pct_below_499 ?? 0
  const freqAbove = latest.freq_pct_above_5005 ?? 0
  const inBand = 100 - freqBelow - freqAbove

  const total = latest.gen_total_mu || GEN_MIX.reduce((a, m) => a + (latest[m.key] || 0), 0)
  const segments = GEN_MIX.map((m) => ({ ...m, pct: total ? ((latest[m.key] || 0) / total) * 100 : 0 })).filter((s) => s.pct > 0)

  return (
    <SectionCard
      title="Live Grid Status"
      subtitle="Latest published NLDC daily figures, updates once per day, not real-time."
      accent="sky"
    >
      <StatGrid>
        <StatCard
          value={fmtMW(demand)}
          label="Peak demand met"
          sub={demandDelta !== null ? `${demandDelta >= 0 ? '+' : ''}${Math.round(demandDelta).toLocaleString('en-IN')} MW vs. prior day` : null}
        />
        <StatCard value={fmtPct(res)} label="RES share of generation" tone="good" />
        <StatCard
          value={fmtPct(inBand)}
          label="Time in normal frequency band"
          sub="49.9–50.05 Hz"
          tone={inBand < 90 ? 'warning' : 'good'}
        />
        <StatCard value={fmtMW((latest.energy_met_total_mu * 1000) / 24)} label="Avg. hourly energy met (approx.)" />
      </StatGrid>

      <div className="mt-5 rounded-2xl border border-white/8 bg-black/20 p-4">
        <div className="mb-3 text-xs font-medium uppercase tracking-wider text-slate-500">Generation mix, latest day</div>
        <div className="flex h-3 w-full overflow-hidden rounded-full border border-white/10">
          {segments.map((s) => (
            <div key={s.name} style={{ width: `${s.pct}%`, background: s.color }} title={`${s.name}: ${s.pct.toFixed(1)}%`} />
          ))}
        </div>
        <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-xs text-slate-400">
          {segments.map((s) => (
            <div key={s.name} className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full" style={{ background: s.color }} />
              {s.name} <span className="text-slate-300">({s.pct.toFixed(1)}%)</span>
            </div>
          ))}
        </div>
      </div>
    </SectionCard>
  )
}
