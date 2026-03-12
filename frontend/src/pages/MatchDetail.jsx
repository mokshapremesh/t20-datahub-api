import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import { PageSpinner } from '../components/Spinner'
import ErrorCard from '../components/ErrorCard'
import { useAuth } from '../auth/AuthContext'
import { teamFlag, teamWithFlag } from '../utils/flags'

function PlayerBrowser({ matchId }) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['squads', matchId],
    queryFn: async () => {
      const r = await api.get(`/matches/${matchId}/squads`)
      return r.data
    },
    enabled: open,
  })

  const teams = Object.entries(data?.players || {})
  const query = search.trim().toLowerCase()
  const filtered = teams.map(([team, players]) => ({
    team,
    players: query ? players.filter(p => p.player_key.toLowerCase().includes(query)) : players,
  })).filter(t => t.players.length > 0)

  const totalPlayers = teams.reduce((sum, [, p]) => sum + p.length, 0)

  return (
    <div className="card overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/[0.03] transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-lg">👥</span>
          <span className="font-medium text-slate-200 text-sm">Players in this match</span>
          {data && (
            <span className="text-xs text-slate-500 bg-white/[0.06] px-2 py-0.5 rounded-full">
              {totalPlayers} players
            </span>
          )}
        </div>
        <span className={`text-slate-400 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}>▾</span>
      </button>

      {open && (
        <div className="border-t border-white/[0.07]">
          {/* Search */}
          <div className="px-4 py-3 border-b border-white/[0.07]">
            <input
              className="input text-sm w-full"
              placeholder="Search players…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              autoFocus
            />
          </div>

          {isLoading ? (
            <div className="px-4 py-6 text-center text-slate-500 text-sm">Loading players…</div>
          ) : filtered.length === 0 ? (
            <div className="px-4 py-6 text-center text-slate-500 text-sm">No players found</div>
          ) : (
            <div className="max-h-96 overflow-y-auto">
              {filtered.map(({ team, players }) => (
                <div key={team} className="border-b border-white/[0.07] last:border-0">
                  <div className="px-4 py-2 bg-white/[0.03] sticky top-0">
                    <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
                      {teamFlag(team) && <span className="mr-1">{teamFlag(team)}</span>}{team}
                      <span className="ml-1 font-normal text-slate-600">({players.length})</span>
                    </p>
                  </div>
                  <div className="divide-y divide-white/[0.04]">
                    {players.map((p, i) => (
                      <div key={p.player_key} className="flex items-center gap-3 px-4 py-2 hover:bg-white/[0.03] transition-colors">
                        <span className="text-slate-600 text-xs font-mono w-5 text-right shrink-0">{i + 1}</span>
                        <span className="text-slate-200 text-sm">{p.player_key}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function MatchDetail() {
  const { matchId } = useParams()
  const { user } = useAuth()

  const { data: match, isLoading, error, refetch } = useQuery({
    queryKey: ['match', matchId],
    queryFn: async () => {
      const r = await api.get(`/matches/${matchId}`)
      return r.data
    },
  })

  if (isLoading) return <PageSpinner />
  if (error) return <ErrorCard error={error} retry={refetch} />
  if (!match) return null

  const date = match.match_date
    ? new Date(match.match_date).toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
    : '—'

  const score1 = match.innings_scores?.[0]
  const score2 = match.innings_scores?.[1]

  return (
    <div className="max-w-3xl mx-auto">
      {/* Breadcrumb */}
      <Link to="/matches" className="text-slate-400 hover:text-slate-200 text-sm inline-flex items-center gap-1 mb-4">
        ← Back to matches
      </Link>

      {/* Hero card */}
      <div className="card p-6 mb-6">
        <div className="flex flex-wrap items-center gap-2 mb-4">
          {match.stage && (
            <span className="badge bg-amber-500/20 text-amber-300">{match.stage}</span>
          )}
          <span className="badge bg-blue-500/20 text-blue-300">{match.tournament_year}</span>
        </div>

        {/* Matchup */}
        <div className="grid grid-cols-3 items-center gap-4 mb-4">
          <div className="text-center">
            <p className={`text-xl font-bold ${match.winner === match.team1 ? 'text-white' : 'text-slate-300'}`}>
              {teamFlag(match.team1) && <span className="block text-2xl mb-0.5">{teamFlag(match.team1)}</span>}
              {match.team1}
            </p>
            {score1 && (
              <p className="font-mono text-lg font-bold text-white mt-1">
                {score1.runs}/{score1.wickets}
                <span className="text-slate-400 text-xs ml-1">({score1.overs})</span>
              </p>
            )}
          </div>

          <div className="text-center">
            <span className="text-slate-500 font-bold text-lg">vs</span>
          </div>

          <div className="text-center">
            <p className={`text-xl font-bold ${match.winner === match.team2 ? 'text-white' : 'text-slate-300'}`}>
              {teamFlag(match.team2) && <span className="block text-2xl mb-0.5">{teamFlag(match.team2)}</span>}
              {match.team2}
            </p>
            {score2 && (
              <p className="font-mono text-lg font-bold text-white mt-1">
                {score2.runs}/{score2.wickets}
                <span className="text-slate-400 text-xs ml-1">({score2.overs})</span>
              </p>
            )}
          </div>
        </div>

        {match.winner && (
          <div className="text-center py-2 bg-emerald-500/10 rounded-lg border border-emerald-500/20">
            <p className="text-emerald-400 font-semibold text-sm">
              🏆 {teamFlag(match.winner) && <span className="mr-1">{teamFlag(match.winner)}</span>}{match.winner} won
            </p>
          </div>
        )}

        {/* Meta */}
        <div className="grid grid-cols-2 gap-3 mt-4 text-sm">
          <div>
            <span className="text-slate-500 text-xs">Date</span>
            <p className="text-slate-300">{date}</p>
          </div>
          <div>
            <span className="text-slate-500 text-xs">Venue</span>
            <p className="text-slate-300">{match.venue || '—'}</p>
          </div>
          {match.toss_winner && (
            <div>
              <span className="text-slate-500 text-xs">Toss</span>
              <p className="text-slate-300">
                {teamFlag(match.toss_winner) && <span className="mr-1">{teamFlag(match.toss_winner)}</span>}
                {match.toss_winner} ({match.toss_decision})
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <Link to={`/matches/${matchId}/scorecard`} className="card p-4 text-center hover:border-white/[0.14] transition-colors group">
          <div className="text-2xl mb-1">📊</div>
          <p className="text-sm font-medium text-slate-300 group-hover:text-white">Scorecard</p>
          <p className="text-xs text-slate-500">Ball-by-ball</p>
        </Link>

        <Link to={`/matches/${matchId}/squads`} className="card p-4 text-center hover:border-white/[0.14] transition-colors group">
          <div className="text-2xl mb-1">👥</div>
          <p className="text-sm font-medium text-slate-300 group-hover:text-white">Squads</p>
          <p className="text-xs text-slate-500">Player pool</p>
        </Link>

        <Link
          to={user ? `/matches/${matchId}/fantasy/teams` : '/login'}
          className="card p-4 text-center hover:border-emerald-500/20 transition-colors group border-emerald-500/10"
        >
          <div className="text-2xl mb-1">✨</div>
          <p className="text-sm font-medium text-emerald-400 group-hover:text-emerald-300">Fantasy</p>
          <p className="text-xs text-slate-500">Build your XI</p>
        </Link>

        <Link to={`/matches/${matchId}/fantasy/leaderboard`} className="card p-4 text-center hover:border-white/[0.14] transition-colors group">
          <div className="text-2xl mb-1">🏅</div>
          <p className="text-sm font-medium text-slate-300 group-hover:text-white">Leaderboard</p>
          <p className="text-xs text-slate-500">Rankings</p>
        </Link>
      </div>

      {/* Player browser */}
      <PlayerBrowser matchId={matchId} />
    </div>
  )
}
