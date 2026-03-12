import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import { PageSpinner } from '../components/Spinner'
import ErrorCard from '../components/ErrorCard'
import { useAuth } from '../auth/AuthContext'
import { teamFlag } from '../utils/flags'

export default function Squads() {
  const { matchId } = useParams()
  const { user } = useAuth()

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['squads', matchId],
    queryFn: async () => {
      const r = await api.get(`/matches/${matchId}/squads`)
      return r.data
    },
  })

  if (isLoading) return <PageSpinner />
  if (error) return <ErrorCard error={error} retry={refetch} />
  if (!data) return null

  const teams = Object.entries(data.players || {})

  return (
    <div className="max-w-4xl mx-auto">
      {/* Breadcrumb */}
      <Link to={`/matches/${matchId}`} className="text-slate-400 hover:text-slate-200 text-sm inline-flex items-center gap-1 mb-4">
        ← {data.matchup}
      </Link>

      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="page-header">Match Squads</h1>
          <p className="page-sub">{data.matchup} · {data.date}</p>
        </div>
        <Link
          to={user ? `/matches/${matchId}/fantasy/teams` : '/login'}
          className="btn-primary"
        >
          ✨ Build Fantasy XI
        </Link>
      </div>

      {/* Team columns */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {teams.map(([teamName, players]) => (
          <div key={teamName} className="card p-4">
            <h2 className="font-bold text-white text-base mb-3 pb-2 border-b border-white/[0.07]">
              {teamFlag(teamName) && <span className="mr-1">{teamFlag(teamName)}</span>}{teamName}
              <span className="text-slate-500 font-normal text-sm ml-2">({players.length} players)</span>
            </h2>
            <div className="flex flex-col gap-0.5">
              {players.map((p, i) => (
                <div
                  key={p.player_key}
                  className="flex items-center justify-between py-2 px-2 rounded hover:bg-white/[0.03] transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-slate-600 text-xs font-mono w-5 text-right">{i + 1}</span>
                    <span className="text-slate-200 text-sm">{p.player_key}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Fantasy CTA */}
      <div className="mt-6 card p-5 flex items-center justify-between gap-4">
        <div>
          <p className="font-semibold text-white">Ready to build your fantasy XI?</p>
          <p className="text-slate-400 text-sm">Pick 11 players, set your captain (2×) and vice-captain (1.5×)</p>
        </div>
        <Link
          to={user ? `/matches/${matchId}/fantasy/teams` : '/login'}
          className="btn-primary shrink-0"
        >
          {user ? 'Build Team' : 'Login to Play'}
        </Link>
      </div>
    </div>
  )
}
