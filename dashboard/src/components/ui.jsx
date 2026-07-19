export function SectionCard({ title, subtitle, children, accent = 'sky' }) {
  const accentBorder = {
    sky: 'border-sky-500/15',
    amber: 'border-amber-500/15',
    violet: 'border-violet-500/15',
    rose: 'border-rose-500/15',
    emerald: 'border-emerald-500/15',
  }[accent]

  return (
    <section
      className={`rounded-3xl border ${accentBorder} bg-[#0d1016]/76 p-6 shadow-[0_0_0_1px_rgba(56,189,248,0.04)] backdrop-blur-sm sm:p-8`}
    >
      {title && (
        <div className="mb-5">
          <h2 className="text-lg font-semibold tracking-tight text-slate-50 sm:text-xl">{title}</h2>
          {subtitle && <p className="mt-1.5 text-sm leading-relaxed text-slate-400">{subtitle}</p>}
        </div>
      )}
      {children}
    </section>
  )
}

export function StatCard({ label, value, sub, tone = 'default' }) {
  const toneClass = {
    default: 'text-slate-50',
    warning: 'text-amber-400',
    critical: 'text-rose-400',
    good: 'text-emerald-400',
  }[tone]

  return (
    <div className="group relative overflow-hidden rounded-2xl border border-white/8 bg-[#0a0c11]/85 p-4 shadow-[0_12px_30px_rgba(0,0,0,0.18)] transition hover:-translate-y-0.5 hover:border-sky-400/25">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-16 bg-gradient-to-b from-white/[0.04] to-transparent" />
      <div className={`relative text-2xl font-semibold tabular-nums tracking-tight ${toneClass}`}>{value}</div>
      <div className="relative mt-1.5 text-[11px] font-medium uppercase tracking-wider text-slate-500">{label}</div>
      {sub && <div className="relative mt-1 text-xs text-slate-400">{sub}</div>}
    </div>
  )
}

export function StatGrid({ children }) {
  return <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">{children}</div>
}

export function Badge({ tone = 'info', children }) {
  const dot = { critical: 'bg-rose-400', warning: 'bg-amber-400', info: 'bg-slate-500', good: 'bg-emerald-400' }[tone]
  const text = { critical: 'text-rose-300', warning: 'text-amber-300', info: 'text-slate-400', good: 'text-emerald-300' }[tone]
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${text}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {children}
    </span>
  )
}

export function Empty({ children }) {
  return <div className="rounded-xl border border-white/6 bg-black/20 px-5 py-10 text-center text-sm text-slate-500">{children}</div>
}

export function ChartTooltip({ active, payload, label, formatter }) {
  if (!active || !payload || !payload.length) return null
  return (
    <div className="rounded-xl border border-white/10 bg-[#0a0c11]/95 px-3 py-2 text-xs shadow-xl backdrop-blur-sm">
      <div className="mb-1 font-semibold text-slate-200">{label}</div>
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2 text-slate-400">
          <span className="h-2 w-2 rounded-full" style={{ background: p.color }} />
          <span>{p.name}:</span>
          <span className="font-medium text-slate-200">{formatter ? formatter(p.value, p.name) : p.value}</span>
        </div>
      ))}
    </div>
  )
}
