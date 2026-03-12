import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { PageSpinner } from '../components/Spinner'
import ErrorCard from '../components/ErrorCard'

export default function FantasyTeamBuilder() {
  const { teamId } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const [actionError, setActionError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')

  const { data: team, isLoading, error, refetch } = useQuery({
    queryKey: ['fantasy-team', teamId],
    queryFn: async () => {
      const r = await api.get(`/fantasy/teams/${teamId}`)
      return r.data
    },
  })

  const { data: squadsData } = useQuery({
    queryKey: ['squads', team?.match_id],
    enabled: !!team?.match_id,
    queryFn: async () => {
      const r = await api.get(`/matches/${team.match_id}/squads`)
      return r.data
    },
  })

  const setCaptainMutation = useMutation({
    mutationFn: async (playerKey) => {
      const r = await api.put(`/fantasy/teams/${teamId}/captain`, null, {
        params: { player_key: playerKey },
      })
      return r.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fantasy-team', teamId] })
      setSuccessMsg('Captain set!')
      setTimeout(() => setSuccessMsg(''), 2000)
    },
    onError: err => setActionError(err?.response?.data?.detail || 'Failed'),
  })

  const setVCMutation = useMutation({
    mutationFn: async (playerKey) => {
      const r = await api.put(`/fantasy/teams/${teamId}/vice-captain`, null, {
        params: { player_key: playerKey },
      })
      return r.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fantasy-team', teamId] })
      setSuccessMsg('Vice-captain set!')
      setTimeout(() => setSuccessMsg(''), 2000)
    },
    onError: err => setActionError(err?.response?.data?.detail || 'Failed'),
  })

  const submitMutation = useMutation({
    mutationFn: async () => {
      const r = await api.post(`/fantasy/teams/${teamId}/submit`)
      return r.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fantasy-team', teamId] })
      setSuccessMsg('Team submitted! 🎉')
    },
    onError: err => setActionError(err?.response?.data?.detail || 'Submission failed'),
  })

  if (isLoading) return <PageSpinner />
  if (error) return <ErrorCard error={error} retry={refetch} />
  if (!team) return null

  const isLocked = team.status === 'SUBMITTED'
  const players = team.player_keys || []
  const captain = team.captain_key
  const vc = team.vice_captain_key
  const playerCount = team.requirements?.current_players || players.length
  const canSubmit = playerCount === 11 && captain && vc && !isLocked

  // Build squads lookup for team colors
  const squadTeams = squadsData?.players || {}
  const playerTeamMap = {}
  Object.entries(squadTeams).forEach(([teamName, plist]) => {
    plist.forEach(p => { playerTeamMap[p.player_key] = teamName })
  })

  return (
    <div className="max-w-3xl mx-auto">
      <Link
        to={team.match_id ? `/matches/${team.match_id}/fantasy/teams` : '/matches'}
        className="text-slate-400 hover:text-slate-200 text-sm inline-flex items-center gap-1 mb-4"
      >
        ← My Teams
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-3 mb-6">
        <div>
          <h1 className="page-header">{team.name}</h1>
          <p className="page-sub">
            {playerCount}/11 players ·{' '}
            {isLocked
              ? <span className="text-emerald-400">Submitted</span>
              : <span className="text-amber-400">Draft</span>
            }
          </p>
        </div>
        {isLocked && team.total_points !== null && (
          <div className="card px-4 py-3 text-right">
            <p className="text-xs text-slate-400">Total Points</p>
            <p className="text-2xl font-bold text-amber-400">{team.total_points}</p>
          </div>
        )}
      </div>

      {/* Status / progress bar */}
      {!isLocked && (
        <div className="card p-4 mb-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-slate-400">Players selected</span>
            <span className="text-xs font-mono text-white">{playerCount}/11</span>
          </div>
          <div className="h-2 bg-white/[0.06] rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${playerCount === 11 ? 'bg-emerald-500' : 'bg-blue-500'}`}
              style={{ width: `${(playerCount / 11) * 100}%` }}
            />
          </div>
          {playerCount < 11 && (
            <p className="text-xs text-slate-500 mt-2">
              You need 11 players. Go to{' '}
              <Link to={`/matches/${team.match_id}/squads`} className="text-emerald-400 hover:underline">
                squads
              </Link>{' '}
              — then{' '}
              <Link to={`/matches/${team.match_id}/fantasy/teams`} className="text-emerald-400 hover:underline">
                recreate
              </Link>{' '}
              your team with player selections.
            </p>
          )}
        </div>
      )}

      {/* Players list */}
      {players.length > 0 && (
        <div className="card p-4 mb-5">
          <h3 className="font-semibold text-white mb-3">Your XI</h3>
          <div className="flex flex-col gap-1">
            {players.map(p => {
              const isCap = p === captain
              const isVC = p === vc
              const teamName = playerTeamMap[p]
              return (
                <div key={p} className={`flex items-center justify-between py-2 px-3 rounded-lg transition-colors ${
                  isCap ? 'bg-amber-500/10' : isVC ? 'bg-blue-500/10' : 'hover:bg-white/[0.03]'
                }`}>
                  <div className="flex items-center gap-2 min-w-0">
                    {isCap && <span className="badge bg-amber-500/20 text-amber-300 text-xs">C</span>}
                    {isVC && <span className="badge bg-blue-500/20 text-blue-300 text-xs">VC</span>}
                    {!isCap && !isVC && <span className="w-6" />}
                    <span className="text-slate-200 text-sm truncate">{p}</span>
                    {teamName && <span className="text-slate-500 text-xs hidden sm:block shrink-0">{teamName}</span>}
                  </div>
                  {!isLocked && (
                    <div className="flex gap-1 shrink-0">
                      <button
                        onClick={() => { setActionError(''); setCaptainMutation.mutate(p) }}
                        disabled={isCap || setCaptainMutation.isPending}
                        className={`text-xs px-2 py-0.5 rounded transition-colors ${
                          isCap
                            ? 'bg-amber-500/20 text-amber-300 cursor-default'
                            : 'text-slate-400 hover:bg-amber-500/10 hover:text-amber-400'
                        }`}
                      >
                        {isCap ? '★ Captain' : 'C'}
                      </button>
                      <button
                        onClick={() => { setActionError(''); setVCMutation.mutate(p) }}
                        disabled={isVC || setVCMutation.isPending}
                        className={`text-xs px-2 py-0.5 rounded transition-colors ${
                          isVC
                            ? 'bg-blue-500/20 text-blue-300 cursor-default'
                            : 'text-slate-400 hover:bg-blue-500/10 hover:text-blue-400'
                        }`}
                      >
                        {isVC ? '★ VC' : 'VC'}
                      </button>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Submit section */}
      {!isLocked && (
        <div className="card p-4 mb-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-medium text-white text-sm">Ready to lock your team?</p>
              <ul className="text-xs text-slate-400 mt-1 space-y-0.5">
                <li className={playerCount === 11 ? 'text-emerald-400' : ''}>
                  {playerCount === 11 ? '✓' : '○'} 11 players selected ({playerCount}/11)
                </li>
                <li className={captain ? 'text-emerald-400' : ''}>
                  {captain ? '✓' : '○'} Captain set {captain ? `(${captain})` : ''}
                </li>
                <li className={vc ? 'text-emerald-400' : ''}>
                  {vc ? '✓' : '○'} Vice-captain set {vc ? `(${vc})` : ''}
                </li>
              </ul>
            </div>
            <button
              onClick={() => { setActionError(''); submitMutation.mutate() }}
              disabled={!canSubmit || submitMutation.isPending}
              className="btn-primary"
            >
              {submitMutation.isPending ? (
                <><span className="spinner w-4 h-4" /> Submitting…</>
              ) : '🚀 Submit team'}
            </button>
          </div>

          {actionError && (
            <p className="text-red-400 text-xs mt-3 bg-red-500/10 border border-red-500/20 rounded px-3 py-2">
              {actionError}
            </p>
          )}
          {successMsg && (
            <p className="text-emerald-400 text-xs mt-3 bg-emerald-500/10 border border-emerald-500/20 rounded px-3 py-2">
              {successMsg}
            </p>
          )}
        </div>
      )}

      {/* Submitted: score breakdown */}
      {isLocked && (
        <div className="card p-4 mb-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-white">Score breakdown</h3>
            <Link
              to={`/matches/${team.match_id}/fantasy/leaderboard`}
              className="btn-secondary text-xs py-1.5"
            >
              🏅 Leaderboard
            </Link>
          </div>
          <p className="text-slate-400 text-sm">
            Total: <span className="text-amber-400 font-bold text-xl">{team.total_points ?? '—'}</span> pts
          </p>
          <p className="text-slate-500 text-xs mt-1">
            Captain ({captain}) earns 2×, Vice-captain ({vc}) earns 1.5×
          </p>
        </div>
      )}
    </div>
  )
}
