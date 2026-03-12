import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts'
import api from '../api/client'
import { PageSpinner } from '../components/Spinner'
import ErrorCard from '../components/ErrorCard'
import { teamFlag } from '../utils/flags'

function StatCard({ label, value, sub, color = 'text-white' }) {
  return (
    <div className="stat-card">
      <p className="stat-label">{label}</p>
      <p className={`stat-val ${color}`}>{value}</p>
      {sub && <p className="text-xs text-slate-500">{sub}</p>}
    </div>
  )
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-surface border border-white/10 rounded-lg px-3 py-2 text-xs">
      <p className="font-semibold text-white mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }}>{p.name}: {p.value}</p>
      ))}
    </div>
  )
}

export default function Dashboard() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['dashboard'],
    queryFn: async () => {
      const r = await api.get('/me/dashboard')
      return r.data
    },
    staleTime: 0,
    refetchOnMount: 'always',
  })

  if (isLoading) return <PageSpinner />
  if (error) {
    if (error?.response?.status === 404) {
      return (
        <div className="max-w-md mx-auto mt-16 text-center">
          <div className="text-5xl mb-4">📊</div>
          <h2 className="text-xl font-bold text-white mb-2">No profile yet</h2>
          <p className="text-slate-400 text-sm mb-6">
            Set your favourite team, player, and year to unlock your personalised dashboard.
          </p>
          <Link to="/me/profile" className="btn-primary">
            Set up profile →
          </Link>
        </div>
      )
    }
    return <ErrorCard error={error} retry={refetch} />
  }

  const { profile, dashboard, scope } = data || {}
  const team = dashboard?.team
  const player = dashboard?.player

  // Year-by-year chart data
  const yearChartData = team?.year_by_year
    ? Object.entries(team.year_by_year).map(([year, v]) => ({
        year,
        Wins: v.wins,
        Losses: v.losses,
        'No result': v.no_results,
      }))
    : []

  // Career history chart
  const careerData = player?.career_wc_history
    ? Object.entries(player.career_wc_history).map(([year, v]) => ({
        year,
        Runs: v.runs,
        Wickets: v.wickets * 20, // scale for visibility
        _wickets: v.wickets,
      }))
    : []

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="page-header">
            {profile?.display_name ? `${profile.display_name}'s Dashboard` : 'My Dashboard'}
          </h1>
          <p className="page-sub">
            {scope?.year ? `T20 World Cup ${scope.year}` : 'All editions'} ·{' '}
            <Link to="/me/profile" className="text-emerald-400 hover:underline">Edit preferences</Link>
          </p>
        </div>
      </div>

      {/* Team block */}
      {team && (
        <section className="mb-8">
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3">
            {teamFlag(team.name) ? teamFlag(team.name) : '🏏'} {team.name}
          </h2>

          {/* Team stat cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
            <StatCard label="Matches" value={team.summary.matches} />
            <StatCard label="Wins" value={team.summary.wins} color="text-emerald-400" />
            <StatCard label="Losses" value={team.summary.losses} color="text-red-400" />
            <StatCard label="Win Rate" value={`${team.summary.win_rate}%`} color="text-amber-400" />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5">
            <StatCard
              label="Avg runs scored/match"
              value={team.batting?.avg_runs_scored_per_match}
              color="text-emerald-400"
            />
            <StatCard
              label="Avg wickets taken/match"
              value={team.bowling?.avg_wickets_per_match}
              color="text-purple-400"
            />
            <StatCard
              label="Death overs economy (vs)"
              value={team.bowling?.death_overs_economy}
              sub="Overs 16–20"
            />
          </div>

          {/* Year-by-year chart */}
          {yearChartData.length > 0 && (
            <div className="card p-4">
              <p className="text-sm font-semibold text-slate-300 mb-3">Year-by-year record</p>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={yearChartData} margin={{ top: 4, right: 16, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="year" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                  <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="Wins" fill="#22c55e" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="Losses" fill="#ef4444" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Stage distribution */}
          {team.stage_distribution && Object.keys(team.stage_distribution).length > 0 && (
            <div className="card p-4 mt-3">
              <p className="text-sm font-semibold text-slate-300 mb-3">Stage appearances</p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(team.stage_distribution).map(([stage, count]) => (
                  <div key={stage} className="flex items-center gap-1.5 bg-white/[0.05] rounded-lg px-3 py-1.5">
                    <span className="text-slate-300 text-sm font-medium">{stage}</span>
                    <span className="text-slate-500 text-xs">×{count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {/* Player block */}
      {player && (
        <section className="mb-8">
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3">
            ⚡ {player.name}
          </h2>

          {/* Warn when player has no data for selected year */}
          {scope?.year &&
            player.tournament.batting.runs === 0 &&
            player.tournament.bowling.wickets === 0 && (
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg px-4 py-3 mb-4 flex items-start gap-2">
              <span className="text-amber-400 shrink-0">⚠</span>
              <p className="text-amber-400/90 text-sm">
                <span className="font-semibold">{player.name}</span> has no recorded stats for {scope.year}.
                {' '}They may not have played, or were injured.{' '}
                <Link to="/me/profile" className="underline hover:text-amber-300">Update your year</Link> to see their best performances.
              </p>
            </div>
          )}

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-5">
            <StatCard label="Runs" value={player.tournament.batting.runs} color="text-blue-400" />
            <StatCard label="Strike Rate" value={player.tournament.batting.strike_rate} />
            <StatCard label="Wickets" value={player.tournament.bowling.wickets} color="text-purple-400" />
            <StatCard label="4s" value={player.tournament.batting.fours} />
            <StatCard label="6s" value={player.tournament.batting.sixes} />
            <StatCard label="Bowling Economy" value={player.tournament.bowling.economy} />
          </div>

          {player.tournament.best_match && (
            <div className="card p-4 mb-3">
              <p className="text-xs text-slate-400 mb-1">Best performance</p>
              <p className="font-semibold text-white">{player.tournament.best_match.label}</p>
              <div className="flex gap-4 mt-1">
                {player.tournament.best_match.wickets > 0 && (
                  <p className="text-purple-400 font-bold text-lg">
                    {player.tournament.best_match.wickets} wkts
                  </p>
                )}
                {player.tournament.best_match.runs > 0 && (
                  <p className="text-emerald-400 font-bold text-lg">
                    {player.tournament.best_match.runs} runs
                  </p>
                )}
                {!player.tournament.best_match.wickets && !player.tournament.best_match.runs && (
                  <p className="text-slate-500 text-sm">0 runs · 0 wickets</p>
                )}
              </div>
            </div>
          )}

          {/* Career chart */}
          {careerData.length > 0 && (
            <div className="card p-4">
              <p className="text-sm font-semibold text-slate-300 mb-3">Career WC history</p>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={careerData} margin={{ top: 4, right: 16, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="year" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                  <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
                  <Tooltip
                    content={({ active, payload, label }) => {
                      if (!active || !payload?.length) return null
                      const runs = payload.find(p => p.dataKey === 'Runs')?.value
                      const wkts = payload.find(p => p.dataKey === 'Wickets')?.payload?._wickets
                      return (
                        <div className="bg-surface border border-white/10 rounded-lg px-3 py-2 text-xs">
                          <p className="font-semibold text-white mb-1">{label}</p>
                          {runs !== undefined && <p className="text-blue-400">Runs: {runs}</p>}
                          {wkts !== undefined && <p className="text-purple-400">Wickets: {wkts}</p>}
                        </div>
                      )
                    }}
                  />
                  <Bar dataKey="Runs" fill="#60a5fa" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="Wickets" fill="#a78bfa" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <p className="text-xs text-slate-600 mt-1 text-center">Wickets bar scaled ×20 for visibility</p>
            </div>
          )}
        </section>
      )}

      {!team && !player && (
        <div className="card p-8 text-center">
          <p className="text-slate-400 mb-4">No data to show yet.</p>
          <Link to="/me/profile" className="btn-primary">
            Update your profile preferences
          </Link>
        </div>
      )}
    </div>
  )
}
