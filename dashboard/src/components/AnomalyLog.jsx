import { SectionCard, Badge, Empty } from './ui'

const HIGH_RISK = 0.5

function buildAnomalies(forecast, risk) {
  const anomalies = []

  forecast.forEach((r) => {
    if (r.actual_mw === null || r.residual_mw === null) return
    const pctErr = Math.abs(r.residual_mw) / r.actual_mw
    if (pctErr >= 0.05) {
      anomalies.push({
        when: r.target_date,
        type: 'Forecast miss',
        severity: pctErr >= 0.1 ? 'critical' : 'warning',
        detail: `Predicted ${Math.round(r.predicted_mw).toLocaleString('en-IN')} MW, actual ${Math.round(r.actual_mw).toLocaleString('en-IN')} MW (${(pctErr * 100).toFixed(1)}% off)`,
      })
    }
  })

  risk.forEach((r) => {
    if (r.violation_prob !== null && r.violation_prob >= HIGH_RISK) {
      anomalies.push({ when: `${r.date} ${r.time}`, type: 'Violation risk', severity: 'critical', detail: `Predicted violation probability ${(r.violation_prob * 100).toFixed(0)}%` })
    }
    if (r.ramp_prob !== null && r.ramp_prob >= HIGH_RISK) {
      anomalies.push({ when: `${r.date} ${r.time}`, type: 'Ramp-shock risk', severity: 'warning', detail: `Predicted ramp-shock probability ${(r.ramp_prob * 100).toFixed(0)}%` })
    }
  })

  return anomalies.sort((a, b) => b.when.localeCompare(a.when))
}

export default function AnomalyLog({ forecast, risk }) {
  const anomalies = buildAnomalies(forecast, risk)

  return (
    <SectionCard
      title="Anomaly Log"
      subtitle="Days where the demand forecast missed by a wide margin, or slots where predicted risk was high. Derived from Study 1/2 model output, not a separate detector."
      accent="rose"
    >
      {!anomalies.length ? (
        <Empty>
          No anomalies in the current logged window. That's the expected, healthy state most days, not a sign that anything is
          broken. Forecast log and risk timeline both grow daily via CI.
        </Empty>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-white/8 bg-gradient-to-b from-sky-500/[0.14] via-[#0a1220] to-black">
          <div className="custom-scrollbar max-h-[420px] overflow-y-auto">
            <table className="w-full min-w-[560px] border-collapse">
              <thead className="sticky top-0 bg-[#0a1220]/95 backdrop-blur-sm">
                <tr>
                  {['When', 'Type', 'Severity', 'Detail'].map((h) => (
                    <th key={h} className="border-b border-white/8 px-4 py-2.5 text-left text-[10.5px] font-semibold uppercase tracking-wider text-slate-500">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {anomalies.slice(0, 50).map((a, i) => (
                  <tr key={i} className="transition hover:bg-white/[0.03]">
                    <td className="border-b border-white/6 px-4 py-2.5 text-xs tabular-nums text-slate-300">{a.when}</td>
                    <td className="border-b border-white/6 px-4 py-2.5 text-xs text-slate-300">{a.type}</td>
                    <td className="border-b border-white/6 px-4 py-2.5 text-xs">
                      <Badge tone={a.severity}>{a.severity}</Badge>
                    </td>
                    <td className="border-b border-white/6 px-4 py-2.5 text-xs text-slate-400">{a.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </SectionCard>
  )
}
