import { useParams, Link, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthContext'
import api from '../api/client'
import { PageSpinner } from '../components/Spinner'
import ErrorCard from '../components/ErrorCard'
import EmptyState from '../components/EmptyState'

function RankBadge({ rank }) {
  if (rank === 1) return <span className="text-2xl">🥇</span>
  if (rank === 2) return <span className="text-2xl">🥈</span>
  if (rank === 3) return <span className="text-2xl">🥉</span>
  return (
    <span className="text-slate-400 font-mono text-sm font-semibold w-7 text-center">
      #{rank}
    </span>
  )
}

export default function MatchLeaderboard() {
  // Works under both /fantasy/matches/:matchId/leaderboard
  // and the legacy /matches/:matchId/fantasy/leaderboard
  const { matchId } = useParams()
  const { user } = useAuth()
  const location = useLocation()
  const isFantasyRoute = location.pathname.startsWith('/fantasy/')

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['match-leaderboard', matchId],
    queryFn: async () => {
      const r = await api.get(`/matches/${matchId}/fantasy/leaderboard`)
      return r.data
    },
  })

  if (isLoading) return <PageSpinner />
  if (error) return <ErrorCard error={error} retry={refetch} />
  if (!data) return null

  const { leaderboard = [] } = data

  return (
    <div className="max-w-2xl mx-auto">
      {/* Breadcrumb — context-aware */}
      <div className="flex items-center gap-3 mb-4">
        <Link
          to={`/fantasy/matches/${matchId}/build`}
          className="text-slate-400 hover:text-slate-200 text-sm inline-flex items-center gap-1"
        >
          ← Build Team
        </Link>
        <span className="text-slate-700">·</span>
        <Link
          to="/fantasy"
          className="text-slate-400 hover:text-slate-200 text-sm"
        >
          Fantasy Home
        </Link>
      </div>

      <div className="mb-6">
        <h1 className="page-header">🏅 Fantasy Leaderboard</h1>
        <p className="page-sub">
          {data.year ? `T20 WC ${data.year}` : `Match ${matchId}`}
          {' · '}{data.total} {data.total === 1 ? 'entry' : 'entries'}
        </p>
      </div>

      {leaderboard.length === 0 ? (
        <EmptyState
          icon="🏅"
          title="No entries yet"
          subtitle="Be the first to submit a fantasy team for this match"
          action={
            user ? (
              <Link to={`/fantasy/matches/${matchId}/build`} className="btn-primary">
                ✨ Build your XI
              </Link>
            ) : (
              <Link to="/login" className="btn-primary">
                Login to play
              </Link>
            )
          }
        />
      ) : (
        <>
          <div className="card overflow-hidden mb-4">
            <table className="table-base w-full">
              <thead>
                <tr>
                  <th className="w-12 text-center">Rank</th>
                  <th>Player</th>
                  <th>Team</th>
                  <th className="text-right">Points</th>
                </tr>
              </thead>
              <tbody>
                {leaderboard.map(entry => (
                  <tr
                    key={entry.rank}
                    className={[
                      entry.rank <= 3 ? 'bg-white/[0.02]' : '',
                      entry.username === user?.username ? 'ring-1 ring-inset ring-emerald-500/30' : '',
                    ].join(' ')}
                  >
                    <td className="text-center">
                      <RankBadge rank={entry.rank} />
                    </td>
                    <td className="font-medium text-slate-200">
                      {entry.username}
                      {entry.username === user?.username && (
                        <span className="text-emerald-400 text-xs ml-1.5">you</span>
                      )}
                    </td>
                    <td className="text-slate-400 text-sm">{entry.team_name}</td>
                    <td className="text-right font-mono font-bold text-amber-400">
                      {entry.total_points}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {user && (
            <Link
              to={`/fantasy/matches/${matchId}/build`}
              className="btn-primary w-full justify-center"
            >
              ✨ Build / Manage your team
            </Link>
          )}
        </>
      )}
    </div>
  )
}
