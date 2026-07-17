import { SectionCard, Badge, Empty } from './ui'

// Fallback only while featureImportance.thresholds hasn't loaded yet -- real
// values come from the freshly-retrained classifiers' VAL-selected best-F1
// threshold (see Pipeline/build_dashboard_data.py), not a guessed constant.
const FALLBACK_THRESHOLDS = { violation: 0.5, ramp: 0.5 }

function buildAnomalies(forecast, risk, thresholds) {
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

  // Severity reflects how far the prediction sits above its OWN threshold, not
  // which type it is. Violation and ramp-shock thresholds are on very different
  // scales (~10.6% vs ~21.4%), so the fair comparison is the ratio to each
  // type's own threshold, not the raw probability: 2x the threshold is "critical"
  // for either type. Without this, an 11% violation (barely over 10.6%) read as
  // more severe than a 68% ramp-shock (more than 3x over 21.4%), which is
  // backwards -- severity should track confidence, not just which model fired.
  const CRITICAL_MULTIPLE = 2

  risk.forEach((r) => {
    if (r.violation_prob !== null && r.violation_prob >= thresholds.violation) {
      const multiple = r.violation_prob / thresholds.violation
      anomalies.push({
        when: `${r.date} ${r.time}`,
        type: 'Violation risk',
        severity: multiple >= CRITICAL_MULTIPLE ? 'critical' : 'warning',
        detail: `Predicted violation probability ${(r.violation_prob * 100).toFixed(0)}% (${multiple.toFixed(1)}x the model's best-F1 threshold, ${(thresholds.violation * 100).toFixed(1)}%)`,
      })
    }
    if (r.ramp_prob !== null && r.ramp_prob >= thresholds.ramp) {
      const multiple = r.ramp_prob / thresholds.ramp
      anomalies.push({
        when: `${r.date} ${r.time}`,
        type: 'Ramp-shock risk',
        severity: multiple >= CRITICAL_MULTIPLE ? 'critical' : 'warning',
        detail: `Predicted ramp-shock probability ${(r.ramp_prob * 100).toFixed(0)}% (${multiple.toFixed(1)}x the model's best-F1 threshold, ${(thresholds.ramp * 100).toFixed(1)}%)`,
      })
    }
  })

  return anomalies.sort((a, b) => b.when.localeCompare(a.when))
}

export default function AnomalyLog({ forecast, risk, thresholds }) {
  const effectiveThresholds = thresholds || FALLBACK_THRESHOLDS
  const anomalies = buildAnomalies(forecast, risk, effectiveThresholds)

  return (
    <SectionCard
      title="Anomaly Log"
      subtitle={`Days where the demand forecast missed by a wide margin, or slots where predicted risk crossed each classifier's own VAL-selected best-F1 threshold (violation ≥ ${(effectiveThresholds.violation * 100).toFixed(1)}%, ramp-shock ≥ ${(effectiveThresholds.ramp * 100).toFixed(1)}%), not an arbitrary round number. Severity is "critical" at 2x that threshold or more, "warning" below it, same rule for both risk types, so severity tracks model confidence, not just which classifier fired. Derived from Study 1/2 model output, not a separate detector.`}
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
