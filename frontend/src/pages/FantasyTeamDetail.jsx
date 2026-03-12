import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthContext'
import api from '../api/client'
import { PageSpinner } from '../components/Spinner'
import ErrorCard from '../components/ErrorCard'

// ── Sub-components ────────────────────────────────────────────────────────────

function ProgressBar({ count }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-slate-400">Players</span>
        <span className={`text-xs font-mono font-bold ${count === 11 ? 'text-emerald-400' : 'text-white'}`}>
          {count}/11
        </span>
      </div>
      <div className="h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${count === 11 ? 'bg-emerald-500' : 'bg-blue-500'}`}
          style={{ width: `${(count / 11) * 100}%` }}
        />
      </div>
    </div>
  )
}

function PlayerList({ players, captain, vc }) {
  return (
    <div className="flex flex-col gap-0.5">
      {players.map((p, i) => {
        const isCap = p === captain
        const isVC = p === vc
        return (
          <div key={p} className={`flex items-center gap-2 px-3 py-2.5 rounded-lg ${
            isCap ? 'bg-amber-500/10' : isVC ? 'bg-blue-500/10' : 'hover:bg-white/[0.03]'
          } transition-colors`}>
            <span className="text-slate-600 text-xs font-mono w-5 text-right">{i + 1}</span>
            <span className="text-slate-200 text-sm flex-1">{p}</span>
            {isCap && <span className="badge bg-amber-500/20 text-amber-300 text-xs">C · 2×</span>}
            {isVC && <span className="badge bg-blue-500/20 text-blue-300 text-xs">VC · 1.5×</span>}
          </div>
        )
      })}
    </div>
  )
}

// ── Submitted view ────────────────────────────────────────────────────────────

function SubmittedView({ team }) {
  const hasPoints = team.total_points !== null && team.total_points !== undefined

  return (
    <div className="flex flex-col gap-4">
      {/* Lock banner */}
      <div className="flex items-center gap-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-4">
        <span className="text-2xl">✅</span>
        <div className="flex-1">
          <p className="font-semibold text-emerald-400">Team Submitted & Locked</p>
          {team.locked_at && (
            <p className="text-xs text-slate-400 mt-0.5">
              Locked {new Date(team.locked_at).toLocaleString('en-GB', {
                day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
              })}
            </p>
          )}
        </div>
        {hasPoints ? (
          <div className="text-right shrink-0">
            <p className="text-xs text-slate-400">Total Points</p>
            <p className="text-3xl font-bold text-amber-400">{team.total_points}</p>
          </div>
        ) : (
          <div className="text-right shrink-0">
            <p className="text-xs text-amber-400/70 font-medium">Points pending</p>
            <p className="text-xs text-slate-500">Calculated after match</p>
          </div>
        )}
      </div>

      {/* Points explanation */}
      {hasPoints ? (
        <div className="card p-4 flex flex-col gap-2">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Scoring</p>
          <div className="flex flex-wrap gap-3 text-sm">
            <span className="text-slate-300">
              Captain{' '}
              <span className="text-amber-400 font-semibold">{team.captain_key}</span>
              {' '}· 2× multiplier
            </span>
            <span className="text-slate-300">
              Vice-captain{' '}
              <span className="text-blue-400 font-semibold">{team.vice_captain_key}</span>
              {' '}· 1.5× multiplier
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Cricket stats live in the{' '}
            <Link to={`/matches/${team.match_id}/scorecard`} className="text-emerald-400 hover:underline">
              scorecard
            </Link>
            . Fantasy points are calculated from ball-by-ball delivery data.
          </p>
        </div>
      ) : (
        <div className="card p-4">
          <p className="text-amber-400 font-medium text-sm">⏳ Points not yet calculated</p>
          <p className="text-slate-400 text-xs mt-1">
            Points appear here once the match data has been fully processed.
          </p>
        </div>
      )}

      {/* XI — read-only */}
      <div className="card p-4">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Your XI (locked)</p>
        <PlayerList
          players={team.player_keys ?? []}
          captain={team.captain_key}
          vc={team.vice_captain_key}
        />
      </div>

      {/* Leaderboard CTA */}
      <Link
        to={`/fantasy/matches/${team.match_id}/leaderboard`}
        className="btn-primary justify-center"
      >
        🏅 View Match Leaderboard
      </Link>
    </div>
  )
}

// ── Draft editor ──────────────────────────────────────────────────────────────

function DraftEditor({ team, qc }) {
  const players = team.player_keys ?? []
  const count = team.requirements?.current_players ?? players.length
  const captain = team.captain_key
  const vc = team.vice_captain_key
  const canSubmit = count === 11 && captain && vc && captain !== vc
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // Re-import useState because this is a nested component defined in this file
  // (react allows this fine, but we define it via module-scope import above)

  const setCaptainMut = useMutation({
    mutationFn: async (playerKey) => {
      const { data } = await api.put(`/fantasy/teams/${team.id}/captain`, null, {
        params: { player_key: playerKey },
      })
      return data
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['fantasy-team', team.id] }); setSuccess('Captain updated'); setTimeout(() => setSuccess(''), 2000) },
    onError: err => setError(err?.response?.data?.detail || 'Failed to set captain'),
  })

  const setVCMut = useMutation({
    mutationFn: async (playerKey) => {
      const { data } = await api.put(`/fantasy/teams/${team.id}/vice-captain`, null, {
        params: { player_key: playerKey },
      })
      return data
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['fantasy-team', team.id] }); setSuccess('Vice-captain updated'); setTimeout(() => setSuccess(''), 2000) },
    onError: err => setError(err?.response?.data?.detail || 'Failed to set vice-captain'),
  })

  const submitMut = useMutation({
    mutationFn: async () => {
      const { data } = await api.post(`/fantasy/teams/${team.id}/submit`)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['fantasy-team', team.id] }),
    onError: err => setError(err?.response?.data?.detail || 'Submit failed'),
  })

  return (
    <div className="flex flex-col gap-5">
      {/* Player count */}
      <div className="card p-4">
        <ProgressBar count={count} />
        {count < 11 && (
          <p className="text-xs text-slate-500 mt-3">
            This team has {count} player{count !== 1 ? 's' : ''}.
            You need exactly 11 to submit. Delete this draft and{' '}
            <Link to={`/fantasy/matches/${team.match_id}/build`} className="text-emerald-400 hover:underline">
              build a new team
            </Link>{' '}
            with 11 players selected.
          </p>
        )}
      </div>

      {/* Players */}
      <div className="card p-4">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
          Selected Players
          <span className="text-slate-600 font-normal ml-2">(player list is fixed at creation)</span>
        </p>
        {players.length === 0 ? (
          <p className="text-slate-500 text-sm py-4 text-center">No players selected</p>
        ) : (
          <PlayerList players={players} captain={captain} vc={vc} />
        )}
      </div>

      {/* Captain & VC — UPDATE actions */}
      <div className="card p-4">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
          Captain & Vice-captain
        </p>
        <p className="text-xs text-slate-500 mb-3">
          Both must be from your selected XI · Captain ≠ Vice-captain
        </p>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-slate-400 mb-1.5">
              Captain <span className="text-amber-400">(2×)</span>
            </label>
            <select
              className="select text-sm"
              value={captain || ''}
              onChange={e => { setError(''); setCaptainMut.mutate(e.target.value) }}
              disabled={players.length === 0 || setCaptainMut.isPending}
            >
              <option value="">Set captain</option>
              {players.map(p => (
                <option key={p} value={p} disabled={p === vc}>{p}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1.5">
              Vice-captain <span className="text-blue-400">(1.5×)</span>
            </label>
            <select
              className="select text-sm"
              value={vc || ''}
              onChange={e => { setError(''); setVCMut.mutate(e.target.value) }}
              disabled={players.length === 0 || setVCMut.isPending}
            >
              <option value="">Set vice-captain</option>
              {players.map(p => (
                <option key={p} value={p} disabled={p === captain}>{p}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Submit checklist */}
      <div className="card p-4">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
          Requirements to Submit
        </p>
        <div className="flex flex-col gap-1.5 mb-4">
          {[
            { ok: count === 11, label: `11 players selected (${count}/11)` },
            { ok: !!captain, label: captain ? `Captain: ${captain}` : 'Captain not set' },
            { ok: !!vc, label: vc ? `Vice-captain: ${vc}` : 'Vice-captain not set' },
            { ok: captain !== vc || (!captain && !vc), label: 'Captain ≠ Vice-captain' },
          ].map(({ ok, label }, i) => (
            <p key={i} className={`text-xs flex items-center gap-1.5 ${ok ? 'text-emerald-400' : 'text-slate-500'}`}>
              <span>{ok ? '✓' : '○'}</span> {label}
            </p>
          ))}
        </div>

        <p className="text-xs text-amber-400/80 bg-amber-500/5 border border-amber-500/10 rounded px-3 py-2 mb-4">
          🔒 Points are revealed only after you submit. Submitting locks your team permanently.
        </p>

        {error && (
          <p className="text-red-400 text-xs bg-red-500/10 border border-red-500/20 rounded px-3 py-2 mb-3">
            {error}
          </p>
        )}
        {success && (
          <p className="text-emerald-400 text-xs bg-emerald-500/10 border border-emerald-500/20 rounded px-3 py-2 mb-3">
            ✓ {success}
          </p>
        )}

        <button
          onClick={() => { setError(''); submitMut.mutate() }}
          disabled={!canSubmit || submitMut.isPending}
          className="btn-primary w-full justify-center"
        >
          {submitMut.isPending
            ? <><span className="spinner w-4 h-4" /> Submitting…</>
            : '🚀 Submit & Lock Team'}
        </button>
      </div>
    </div>
  )
}

// ── Need useState for DraftEditor above ──────────────────────────────────────
import { useState } from 'react'

// ── Main component ────────────────────────────────────────────────────────────

export default function FantasyTeamDetail() {
  const { teamId } = useParams()
  const qc = useQueryClient()

  const { data: team, isLoading, error, refetch } = useQuery({
    queryKey: ['fantasy-team', Number(teamId)],
    queryFn: async () => {
      const { data } = await api.get(`/fantasy/teams/${teamId}`)
      return data
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async () => { await api.delete(`/fantasy/teams/${teamId}`) },
  })

  if (isLoading) return <PageSpinner />
  if (error) return <ErrorCard error={error} retry={refetch} />
  if (!team) return null

  const isLocked = team.status === 'SUBMITTED'

  return (
    <div className="max-w-xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-3 mb-4 text-sm">
        <Link to={`/fantasy/matches/${team.match_id}/build`}
          className="text-slate-400 hover:text-slate-200 inline-flex items-center gap-1">
          ← Build page
        </Link>
        <span className="text-slate-700">·</span>
        <Link to="/fantasy" className="text-slate-400 hover:text-slate-200">Fantasy</Link>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-5">
        <div>
          <h1 className="page-header">{team.name}</h1>
          <div className="flex items-center gap-2 mt-1">
            <span className={`badge ${isLocked ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'}`}>
              {isLocked ? 'Submitted' : 'Draft'}
            </span>
          </div>
        </div>
        {/* Delete only on DRAFT */}
        {!isLocked && (
          <button
            onClick={async () => {
              if (!confirm('Permanently delete this draft team?')) return
              try {
                await deleteMutation.mutateAsync()
                window.history.back()
              } catch (err) {
                alert(err?.response?.data?.detail || 'Could not delete')
              }
            }}
            className="btn-danger text-xs py-1.5"
          >
            🗑 Delete Draft
          </button>
        )}
      </div>

      {/* Content — Submitted vs Draft */}
      {isLocked ? (
        <SubmittedView team={team} />
      ) : (
        <DraftEditor team={team} qc={qc} />
      )}
    </div>
  )
}
