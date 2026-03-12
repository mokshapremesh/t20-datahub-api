import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-center">
      <span className="text-6xl">🏏</span>
      <h1 className="text-3xl font-bold text-white">404</h1>
      <p className="text-slate-400">Page not found</p>
      <Link to="/matches" className="btn-primary mt-2">
        Back to matches
      </Link>
    </div>
  )
}
