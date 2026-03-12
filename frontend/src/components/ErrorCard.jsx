export default function ErrorCard({ error, retry }) {
  const msg = error?.response?.data?.detail || error?.message || 'Something went wrong'
  return (
    <div className="card p-6 flex flex-col items-center gap-3 text-center max-w-md mx-auto mt-8">
      <div className="text-3xl">⚠️</div>
      <p className="text-slate-300 font-medium">{msg}</p>
      {retry && (
        <button onClick={retry} className="btn-secondary text-sm">
          Try again
        </button>
      )}
    </div>
  )
}
