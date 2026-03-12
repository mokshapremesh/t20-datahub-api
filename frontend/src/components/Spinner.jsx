export default function Spinner({ className = '' }) {
  return (
    <div className={`flex items-center justify-center ${className}`}>
      <div className="spinner" />
    </div>
  )
}

export function PageSpinner() {
  return (
    <div className="flex items-center justify-center min-h-[40vh]">
      <div className="flex flex-col items-center gap-3">
        <div className="spinner w-8 h-8 border-[3px]" />
        <p className="text-slate-500 text-sm">Loading…</p>
      </div>
    </div>
  )
}
