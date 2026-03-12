import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import { PageSpinner } from '../components/Spinner'
import ErrorCard from '../components/ErrorCard'
import { teamFlag } from '../utils/flags'

function BattingTable({ rows }) {
  return (
    <div className="overflow-x-auto">
      <table className="table-base w-full text-xs sm:text-sm">
        <thead>
          <tr>
            <th className="text-left">Batter</th>
            <th>Dismissal</th>
            <th className="text-right">R</th>
            <th className="text-right">B</th>
            <th className="text-right">4s</th>
            <th className="text-right">6s</th>
            <th className="text-right">SR</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className={r.dismissal === 'not out' ? 'text-emerald-300/90' : ''}>
              <td className="font-medium whitespace-nowrap">{r.batter}</td>
              <td className="text-slate-400 text-xs">{r.dismissal}</td>
              <td className="text-right font-mono font-bold text-white">{r.runs}</td>
              <td className="text-right font-mono">{r.balls}</td>
              <td className="text-right font-mono">{r.fours}</td>
              <td className="text-right font-mono">{r.sixes}</td>
              <td className="text-right font-mono text-slate-400">{r.strike_rate}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function BowlingTable({ rows }) {
  return (
    <div className="overflow-x-auto mt-4">
      <table className="table-base w-full text-xs sm:text-sm">
        <thead>
          <tr>
            <th className="text-left">Bowler</th>
            <th className="text-right">O</th>
            <th className="text-right">M</th>
            <th className="text-right">R</th>
            <th className="text-right">W</th>
            <th className="text-right">Econ</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td className="font-medium whitespace-nowrap">{r.bowler}</td>
              <td className="text-right font-mono">{r.overs}</td>
              <td className="text-right font-mono">{r.maidens}</td>
              <td className="text-right font-mono">{r.runs}</td>
              <td className="text-right font-mono font-bold text-white">{r.wickets}</td>
              <td className={`text-right font-mono ${r.economy < 7 ? 'text-emerald-400' : r.economy > 10 ? 'text-red-400' : 'text-slate-300'}`}>
                {r.economy}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function FoWLine({ fow }) {
  if (!fow?.length) return null
  return (
    <div className="mt-4 pt-3 border-t border-white/[0.07]">
      <p className="text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wide">Fall of Wickets</p>
      <div className="flex flex-wrap gap-2">
        {fow.map((f, i) => (
          <span key={i} className="text-xs bg-white/[0.05] rounded px-2 py-0.5 font-mono text-slate-300">
            {f.score} <span className="text-slate-500">({f.player}, {f.over})</span>
          </span>
        ))}
      </div>
    </div>
  )
}

function InningsCard({ inn }) {
  return (
    <div className="card p-4">
      {/* Innings header */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <div>
          <h3 className="font-bold text-white text-base">
            {teamFlag(inn.batting_team) && <span className="mr-1">{teamFlag(inn.batting_team)}</span>}{inn.batting_team}
          </h3>
          <p className="text-slate-400 text-xs">
            bowling: {teamFlag(inn.bowling_team) && <span className="mr-1">{teamFlag(inn.bowling_team)}</span>}{inn.bowling_team}
          </p>
        </div>
        <div className="text-right">
          <p className="font-mono text-2xl font-bold text-white">
            {inn.summary.runs}/{inn.summary.wkts}
          </p>
          <p className="text-slate-400 text-xs">
            {inn.summary.overs} overs · RR {inn.summary.run_rate}
          </p>
          {inn.extras?.total > 0 && (
            <p className="text-slate-500 text-xs">
              Extras {inn.extras.total}
              {inn.extras.wides > 0 ? ` (wd ${inn.extras.wides})` : ''}
              {inn.extras.noballs > 0 ? ` (nb ${inn.extras.noballs})` : ''}
            </p>
          )}
        </div>
      </div>

      <BattingTable rows={inn.batting} />
      <BowlingTable rows={inn.bowling} />
      <FoWLine fow={inn.fall_of_wkts} />
    </div>
  )
}

export default function Scorecard() {
  const { matchId } = useParams()
  const [activeInnings, setActiveInnings] = useState(null) // null = all

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['scorecard', matchId],
    queryFn: async () => {
      const r = await api.get(`/matches/${matchId}/scorecard`, {
        params: { include: 'fow' },
      })
      return r.data
    },
  })

  if (isLoading) return <PageSpinner />
  if (error) return <ErrorCard error={error} retry={refetch} />
  if (!data) return null

  const { match, innings } = data

  const displayInnings = activeInnings === null
    ? innings
    : innings.filter(i => i.innings_no === activeInnings)

  return (
    <div className="max-w-4xl mx-auto">
      {/* Breadcrumb */}
      <Link to={`/matches/${matchId}`} className="text-slate-400 hover:text-slate-200 text-sm inline-flex items-center gap-1 mb-4">
        ← {match.team1} vs {match.team2}
      </Link>

      {/* Match header */}
      <div className="card p-4 mb-5">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          {match.stage && <span className="badge bg-amber-500/20 text-amber-300">{match.stage}</span>}
          <span className="badge bg-blue-500/20 text-blue-300">{match.tournament_year}</span>
        </div>
        <h1 className="text-lg font-bold text-white">
          {teamFlag(match.team1) && <span className="mr-1">{teamFlag(match.team1)}</span>}{match.team1}
          {' vs '}
          {teamFlag(match.team2) && <span className="mr-1">{teamFlag(match.team2)}</span>}{match.team2}
        </h1>
        <p className="text-slate-400 text-sm">{match.venue}</p>
        {match.winner && (
          <p className="text-emerald-400 text-sm mt-1 font-medium">
            🏆 {teamFlag(match.winner) && <span className="mr-1">{teamFlag(match.winner)}</span>}{match.winner} won
          </p>
        )}
      </div>

      {/* Innings tabs */}
      {innings.length > 1 && (
        <div className="flex gap-1 mb-4 p-1 bg-white/[0.04] rounded-lg w-fit">
          <button
            onClick={() => setActiveInnings(null)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
              activeInnings === null ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            All innings
          </button>
          {innings.map(inn => (
            <button
              key={inn.innings_no}
              onClick={() => setActiveInnings(inn.innings_no)}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
                activeInnings === inn.innings_no ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {teamFlag(inn.batting_team) && <span className="mr-1">{teamFlag(inn.batting_team)}</span>}{inn.batting_team} inn
            </button>
          ))}
        </div>
      )}

      {/* Innings cards */}
      <div className="flex flex-col gap-5">
        {displayInnings.map(inn => (
          <InningsCard key={inn.innings_no} inn={inn} />
        ))}
      </div>
    </div>
  )
}
