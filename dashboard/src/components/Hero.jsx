export default function Hero({ asOfDate }) {
  return (
    <section className="relative overflow-hidden rounded-3xl border border-sky-400/30 bg-[#111722]/90 p-8 text-center shadow-[0_0_0_1px_rgba(56,189,248,0.12),0_25px_80px_-20px_rgba(56,189,248,0.35),0_10px_40px_-10px_rgba(0,0,0,0.6)] backdrop-blur-sm sm:p-12">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-sky-400/[0.14] to-transparent" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-sky-400/60 to-transparent" />
      <div className="relative">
        <h1 className="bg-gradient-to-b from-white to-slate-300 bg-clip-text text-4xl font-extrabold tracking-tight text-transparent sm:text-5xl">
          Grid-Sentinel
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-sm leading-relaxed text-slate-400 sm:text-base">
          Indian power grid stress monitoring, built on{' '}
          <span className="font-medium text-slate-300">7 years of NLDC daily and live SCADA data</span> across three
          research eras: daily corridor visibility (2019), cross-border transparency (2023), and full live 15-minute
          SCADA (2024–present).
        </p>
        <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3.5 py-1.5 text-[11px] font-medium text-slate-400">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          {asOfDate ? `Data as of ${asOfDate}` : 'Loading…'}
        </div>
      </div>
    </section>
  )
}
