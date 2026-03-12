import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import api from '../api/client'
import { PageSpinner } from '../components/Spinner'
import ErrorCard from '../components/ErrorCard'
import EmptyState from '../components/EmptyState'
import { teamFlag } from '../utils/flags'

const STAGES = ['Final', 'Semi Final', 'Super 8', 'Group']

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

function MatchCard({ match }) {
  const score1 = match.innings_scores?.[0]
  const score2 = match.innings_scores?.[1]

  return (
    <div className="card p-4 hover:border-white/[0.14] transition-colors group">
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex flex-col gap-1 min-w-0">
          {stageBadge(match.stage)}
          <span className="text-xs text-slate-500 mt-1">
            {match.tournament_year} · {match.venue || 'Unknown venue'}
          </span>
        </div>
        {match.winner && (
          <span className="badge bg-emerald-500/15 text-emerald-400 shrink-0">
            🏆 {teamFlag(match.winner) && <span className="mr-0.5">{teamFlag(match.winner)}</span>}{match.winner}
          </span>
        )}
      </div>

      {/* Teams & scores */}
      <div className="space-y-2 mb-4">
        {[{ team: match.team1, score: score1 }, { team: match.team2, score: score2 }].map(({ team, score }, i) => (
          <div key={i} className="flex items-center justify-between">
            <span className={`font-semibold text-sm ${match.winner === team ? 'text-white' : 'text-slate-300'}`}>
              {teamFlag(team) && <span className="mr-1">{teamFlag(team)}</span>}{team}
            </span>
            {score ? (
              <span className="font-mono text-sm text-slate-300">
                <span className="text-white font-bold">{score.runs}/{score.wickets}</span>
                <span className="text-slate-500 text-xs ml-1">({score.overs})</span>
              </span>
            ) : (
              <span className="text-slate-600 text-xs">—</span>
            )}
          </div>
        ))}
      </div>

      {/* Date */}
      <p className="text-xs text-slate-500 mb-3">
        {match.match_date ? new Date(match.match_date).toLocaleDateString('en-GB', {
          day: 'numeric', month: 'short', year: 'numeric'
        }) : '—'}
      </p>

      {/* Actions */}
      <div className="flex gap-2 flex-wrap">
        <Link
          to={`/matches/${match.id}/scorecard`}
          className="text-xs px-2.5 py-1 rounded bg-white/[0.06] hover:bg-white/[0.10] text-slate-300 transition-colors"
        >
          📊 Scorecard
        </Link>
      </div>
    </div>
  )
}

function SkeletonCard() {
  return (
    <div className="card p-4 animate-pulse">
      <div className="h-4 w-20 bg-white/[0.06] rounded mb-3" />
      <div className="space-y-2 mb-3">
        <div className="flex justify-between">
          <div className="h-4 w-24 bg-white/[0.06] rounded" />
          <div className="h-4 w-16 bg-white/[0.06] rounded" />
        </div>
        <div className="flex justify-between">
          <div className="h-4 w-20 bg-white/[0.06] rounded" />
          <div className="h-4 w-16 bg-white/[0.06] rounded" />
        </div>
      </div>
      <div className="h-3 w-28 bg-white/[0.04] rounded mb-3" />
      <div className="flex gap-2">
        <div className="h-6 w-20 bg-white/[0.04] rounded" />
        <div className="h-6 w-16 bg-white/[0.04] rounded" />
      </div>
    </div>
  )
}

export default function Matches() {
  const [filters, setFilters] = useState({ team: '', year: '', stage: '', venue: '' })
  const [applied, setApplied] = useState({})

  const { data: yearsData } = useQuery({
    queryKey: ['options-years'],
    queryFn: async () => { const r = await api.get('/options/years'); return r.data },
    staleTime: Infinity,
  })
  const years = yearsData?.years ?? []

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['matches', applied],
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

  const resetFilters = () => {
    setFilters({ team: '', year: '', stage: '', venue: '' })
    setApplied({})
  }

  const matches = data?.matches || []

  return (
    <div>
      {/* Page header */}
      <div className="mb-6">
        <h1 className="page-header">T20 World Cup Matches</h1>
        <p className="page-sub">Ball-by-ball data from 2014–2026 · {data?.total ?? '—'} matches total</p>
      </div>

      {/* Filters */}
      <form onSubmit={applyFilters} className="card p-4 mb-6">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Year</label>
            <select
              className="select"
              value={filters.year}
              onChange={e => setFilters(f => ({ ...f, year: e.target.value }))}
            >
              <option value="">All years</option>
              {years.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Stage</label>
            <select
              className="select"
              value={filters.stage}
              onChange={e => setFilters(f => ({ ...f, stage: e.target.value }))}
            >
              <option value="">All stages</option>
              {STAGES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Team</label>
            <input
              className="input"
              placeholder="e.g. India"
              value={filters.team}
              onChange={e => setFilters(f => ({ ...f, team: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Venue</label>
            <input
              className="input"
              placeholder="e.g. MCG"
              value={filters.venue}
              onChange={e => setFilters(f => ({ ...f, venue: e.target.value }))}
            />
          </div>
        </div>
        <div className="flex gap-2 mt-3">
          <button type="submit" className="btn-primary text-xs py-1.5">Apply filters</button>
          <button type="button" onClick={resetFilters} className="btn-secondary text-xs py-1.5">Reset</button>
        </div>
      </form>

      {/* Results */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 9 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : error ? (
        <ErrorCard error={error} retry={refetch} />
      ) : matches.length === 0 ? (
        <EmptyState
          icon="🏏"
          title="No matches found"
          subtitle="Try adjusting your filters"
          action={<button onClick={resetFilters} className="btn-secondary">Clear filters</button>}
        />
      ) : (
        <>
          <p className="text-slate-500 text-xs mb-3">{matches.length} matches</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {matches.map(m => <MatchCard key={m.id} match={m} />)}
          </div>
        </>
      )}
    </div>
  )
}
