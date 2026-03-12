import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import api from '../api/client'
import { PageSpinner } from '../components/Spinner'
import ErrorCard from '../components/ErrorCard'
import EmptyState from '../components/EmptyState'
import { useAuth } from '../auth/AuthContext'

const YEARS = ['2024', '2022', '2021', '2020', '2019', '2018', '2016', '2015', '2014']
const STAGES = ['Final', 'Semi Final', 'Super 12', 'Super 8', 'Super 4', 'Group']

function stageBadge(stage) {
  if (!stage) return null
  const s = stage.toLowerCase()
  let cls = 'badge '
  if (s.includes('final') && !s.includes('semi')) cls += 'bg-amber-500/20 text-amber-300'
  else if (s.includes('semi')) cls += 'bg-purple-500/20 text-purple-300'
  else if (s.includes('super')) cls += 'bg-blue-500/20 text-blue-300'
  else cls += 'bg-slate-700 text-slate-300'
  return <span className={cls}>{stage}</span>
}

// Fantasy cards intentionally hide match results (scores, winner).
// Scorecards live in the Matches section only.
function FantasyMatchCard({ match, user }) {
  const venue = match.venue || 'Unknown venue'
  const dateStr = match.match_date
    ? new Date(match.match_date).toLocaleDateString('en-GB', {
        day: 'numeric', month: 'short', year: 'numeric',
      })
    : 'Date unknown'

  return (
    <div className="card p-4 hover:border-white/[0.14] transition-all flex flex-col gap-3">
      {/* Stage + year — no winner badge */}
      <div className="flex items-center gap-2 flex-wrap">
        {stageBadge(match.stage)}
        <span className="text-xs text-slate-500">{match.tournament_year || '—'}</span>
      </div>

      {/* Teams — neutral display, no score, no winner highlight */}
      <div className="flex items-center gap-3">
        <span className="font-bold text-white text-base flex-1 text-right">{match.team1}</span>
        <span className="text-slate-500 font-medium text-sm shrink-0">vs</span>
        <span className="font-bold text-white text-base flex-1">{match.team2}</span>
      </div>

      {/* Venue + date — no scores */}
      <p className="text-xs text-slate-500 truncate">
        {venue} · {dateStr}
      </p>

      {/* CTAs */}
      <div className="flex gap-2 pt-1 border-t border-white/[0.05]">
        {user ? (
          <Link
            to={`/fantasy/matches/${match.id}/build`}
            className="btn-primary text-xs py-1.5 flex-1 justify-center"
          >
            ✨ Build Team
          </Link>
        ) : (
          <Link
            to="/login"
            state={{ from: { pathname: `/fantasy/matches/${match.id}/build` } }}
            className="btn-primary text-xs py-1.5 flex-1 justify-center"
          >
            Login to Play
          </Link>
        )}
        <Link
          to={`/fantasy/matches/${match.id}/leaderboard`}
          className="btn-secondary text-xs py-1.5 px-3 shrink-0"
          title="Match leaderboard"
        >
          🏅
        </Link>
      </div>
    </div>
  )
}

function SkeletonCard() {
  return (
    <div className="card p-4 animate-pulse flex flex-col gap-3">
      <div className="h-4 w-20 bg-white/[0.06] rounded" />
      <div className="flex items-center gap-3">
        <div className="h-5 flex-1 bg-white/[0.06] rounded" />
        <div className="h-4 w-5 bg-white/[0.04] rounded" />
        <div className="h-5 flex-1 bg-white/[0.06] rounded" />
      </div>
      <div className="h-3 w-40 bg-white/[0.04] rounded" />
      <div className="flex gap-2 pt-1">
        <div className="h-7 flex-1 bg-white/[0.06] rounded-lg" />
        <div className="h-7 w-10 bg-white/[0.04] rounded-lg" />
      </div>
    </div>
  )
}

export default function Fantasy() {
  const { user } = useAuth()
  const [filters, setFilters] = useState({ team: '', year: '', stage: '' })
  const [applied, setApplied] = useState({})

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['fantasy-matches', applied],
    queryFn: async () => {
      const params = Object.fromEntries(Object.entries(applied).filter(([, v]) => v))
      const r = await api.get('/matches', { params })
      return r.data
    },
  })

  const applyFilters = e => {
    e.preventDefault()
    setApplied({ ...filters })
  }

  const reset = () => {
    setFilters({ team: '', year: '', stage: '' })
    setApplied({})
  }

  const matches = data?.matches || []

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-1">
          <span className="text-3xl">✨</span>
          <h1 className="text-2xl font-bold text-white">Fantasy Cricket</h1>
        </div>
        <p className="text-slate-400 text-sm">
          Pick a match · Build your XI · Set C & VC · Submit to earn points
        </p>
        {!user && (
          <div className="mt-3 inline-flex items-center gap-2 text-sm bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-4 py-2 text-emerald-400">
            <span>🔒</span>
            <span>
              <Link to="/login" className="font-semibold underline underline-offset-2">Sign in</Link>
              {' '}or{' '}
              <Link to="/register" className="font-semibold underline underline-offset-2">register</Link>
              {' '}to play
            </span>
          </div>
        )}
      </div>

      {/* How it works */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-6">
        {[
          { icon: '🔍', label: 'Pick a match' },
          { icon: '👥', label: 'Select your XI' },
          { icon: '⭐', label: 'Set C & VC' },
          { icon: '🚀', label: 'Submit for points' },
        ].map(({ icon, label }, i) => (
          <div key={i} className="card p-3 flex items-center gap-2.5">
            <span className="text-lg shrink-0">{icon}</span>
            <p className="text-xs font-medium text-slate-300">{label}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <form onSubmit={applyFilters} className="card p-4 mb-5">
        <p className="text-xs font-semibold text-slate-400 mb-3 uppercase tracking-wide">
          Choose a contest
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Year</label>
            <select className="select" value={filters.year}
              onChange={e => setFilters(f => ({ ...f, year: e.target.value }))}>
              <option value="">All years</option>
              {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Stage</label>
            <select className="select" value={filters.stage}
              onChange={e => setFilters(f => ({ ...f, stage: e.target.value }))}>
              <option value="">All stages</option>
              {STAGES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Team</label>
            <input className="input" placeholder="e.g. India" value={filters.team}
              onChange={e => setFilters(f => ({ ...f, team: e.target.value }))} />
          </div>
        </div>
        <div className="flex gap-2 mt-3">
          <button type="submit" className="btn-primary text-xs py-1.5">Find matches</button>
          <button type="button" onClick={reset} className="btn-secondary text-xs py-1.5">Reset</button>
        </div>
      </form>

      {/* Match grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : error ? (
        <ErrorCard error={error} retry={refetch} />
      ) : matches.length === 0 ? (
        <EmptyState icon="🏏" title="No matches found" subtitle="Try adjusting the filters"
          action={<button onClick={reset} className="btn-secondary">Reset</button>} />
      ) : (
        <>
          <p className="text-slate-500 text-xs mb-3">{matches.length} matches available</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {matches.map(m => <FantasyMatchCard key={m.id} match={m} user={user} />)}
          </div>
        </>
      )}
    </div>
  )
}
