import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import { PageSpinner } from '../components/Spinner'
import ErrorCard from '../components/ErrorCard'
import EmptyState from '../components/EmptyState'

const YEARS = ['2024', '2022', '2021', '2020', '2019', '2018', '2016', '2015', '2014']

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

export default function GlobalLeaderboard() {
  const [year, setYear] = useState('')

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['global-leaderboard', year],
    queryFn: async () => {
      const params = year ? { year } : {}
      const r = await api.get('/fantasy/leaderboard', { params })
      return r.data
    },
  })

  const leaderboard = data?.leaderboard || []

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-6">
        <h1 className="page-header">🌍 Global Leaderboard</h1>
        <p className="page-sub">Fantasy rankings across all T20 World Cup matches</p>
      </div>

      {/* Year filter */}
      <div className="flex items-center gap-3 mb-5">
        <select
          className="select w-40"
          value={year}
          onChange={e => setYear(e.target.value)}
        >
          <option value="">All years</option>
          {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
        </select>
        {data?.total !== undefined && (
          <span className="text-slate-400 text-sm">{data.total} entries</span>
        )}
      </div>

      {isLoading ? (
        <PageSpinner />
      ) : error ? (
        <ErrorCard error={error} retry={refetch} />
      ) : leaderboard.length === 0 ? (
        <EmptyState
          icon="🏅"
          title="No entries yet"
          subtitle="Play fantasy on any match to appear here"
        />
      ) : (
        <div className="card overflow-hidden">
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
                  key={`${entry.rank}-${entry.username}`}
                  className={entry.rank <= 3 ? 'bg-white/[0.02]' : ''}
                >
                  <td className="text-center">
                    <RankBadge rank={entry.rank} />
                  </td>
                  <td className="font-medium text-slate-200">{entry.username}</td>
                  <td className="text-slate-400 text-sm">{entry.team_name}</td>
                  <td className="text-right font-mono font-bold text-amber-400">
                    {entry.total_points}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
