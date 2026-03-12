export default function EmptyState({ icon = '📭', title, subtitle, action }) {
  return (
    <div className="card p-10 flex flex-col items-center gap-3 text-center">
      <div className="text-4xl">{icon}</div>
      <p className="font-semibold text-slate-200">{title}</p>
      {subtitle && <p className="text-slate-400 text-sm max-w-xs">{subtitle}</p>}
      {action}
    </div>
  )
}
