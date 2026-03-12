import { useState, useMemo } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { PageSpinner } from '../components/Spinner'
import ErrorCard from '../components/ErrorCard'
import { teamFlag } from '../utils/flags'

// ── Build helpers ──────────────────────────────────────────────────────────────

async function createTeam(matchId, name, playerKeys, captainKey, vcKey, submit) {
  const p = new URLSearchParams()
  p.append('name', name.trim())
  playerKeys.filter(Boolean).forEach(k => p.append('player_keys', k))

  const { data: team } = await api.post(`/matches/${matchId}/fantasy/teams?${p.toString()}`)
  const teamId = team.id

  if (captainKey) {
    await api.put(`/fantasy/teams/${teamId}/captain`, null, { params: { player_key: captainKey } })
  }
  if (vcKey) {
    await api.put(`/fantasy/teams/${teamId}/vice-captain`, null, { params: { player_key: vcKey } })
  }
  if (submit) {
    const { data: submitted } = await api.post(`/fantasy/teams/${teamId}/submit`)
    return submitted
  }
  const { data: refreshed } = await api.get(`/fantasy/teams/${teamId}`)
  return refreshed
}

function friendlyError(err) {
  const status = err?.response?.status
  const detail = err?.response?.data?.detail
  if (status === 401) return 'You must be logged in to build a team.'
  if (status === 403) return 'You do not have permission to do this.'
  if (status === 404) return 'Match not found.'
  if (status === 400 && typeof detail === 'string') return detail
  if (status === 422) return 'Invalid request — check your selections and try again.'
  if (status >= 500) return 'Server error — please try again shortly.'
  if (typeof detail === 'string') return detail
  return 'Something went wrong. Please try again.'
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function StatusBadge({ status }) {
  if (status === 'SUBMITTED')
    return <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400">Submitted</span>
  return <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400">Draft</span>
}

function TeamRow({ team, onDelete, isDeleting }) {
  const count = team.player_keys?.length ?? 0
  return (
    <div className="flex items-center justify-between gap-3 p-3 rounded-lg bg-white/[0.03] hover:bg-white/[0.05] transition-colors">
      <div className="flex items-center gap-2.5 min-w-0">
        <StatusBadge status={team.status} />
        <div className="min-w-0">
          <p className="font-semibold text-white text-sm truncate">{team.name}</p>
          <p className="text-xs text-slate-500">
            {count}/11 players
            {team.captain_key && <> · C: <span className="text-amber-400">{team.captain_key}</span></>}
            {team.vice_captain_key && <> · VC: <span className="text-blue-400">{team.vice_captain_key}</span></>}
            {team.status === 'SUBMITTED' && team.total_points != null && (
              <> · <span className="text-amber-400 font-bold">{team.total_points} pts</span></>
            )}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <Link
          to={`/fantasy/teams/${team.id}`}
          className="btn-secondary text-xs py-1 px-2.5"
        >
          {team.status === 'SUBMITTED' ? 'View' : 'Continue →'}
        </Link>
        {team.status === 'DRAFT' && (
          <button
            onClick={() => onDelete(team.id)}
            disabled={isDeleting}
            className="text-xs px-2.5 py-1 rounded text-red-400/60 hover:text-red-400 hover:bg-red-500/10 transition-colors"
          >
            Delete
          </button>
        )}
      </div>
    </div>
  )
}

// Collapsible squad section
function SquadSection({ teamName, players, selectedSet, filledCount, onAdd }) {
  const [open, setOpen] = useState(true)
  const available = players.filter(p => !selectedSet.has(p.player_key))
  const added = players.filter(p => selectedSet.has(p.player_key))

  return (
    <div className="border border-white/[0.07] rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-3 py-2.5 bg-white/[0.04] hover:bg-white/[0.06] transition-colors"
      >
        <span className="text-sm font-semibold text-white">
          {teamFlag(teamName) && <span className="mr-1">{teamFlag(teamName)}</span>}{teamName}
        </span>
        <span className="text-xs text-slate-400">
          {added.length} added · {players.length} total {open ? '▲' : '▼'}
        </span>
      </button>
      {open && (
        <div className="divide-y divide-white/[0.04]">
          {players.map(p => {
            const inXI = selectedSet.has(p.player_key)
            const full = filledCount >= 11 && !inXI
            return (
              <div
                key={p.player_key}
                className={`flex items-center justify-between px-3 py-2 text-sm ${
                  inXI ? 'bg-emerald-500/5' : ''
                }`}
              >
                <span className={inXI ? 'text-emerald-400/70' : 'text-slate-300'}>{p.player_key}</span>
                {inXI ? (
                  <span className="text-[11px] text-emerald-500/80 font-medium">✓ In XI</span>
                ) : (
                  <button
                    onClick={() => onAdd(p.player_key)}
                    disabled={full}
                    className={`text-xs px-2.5 py-1 rounded transition-colors ${
                      full
                        ? 'text-slate-600 cursor-not-allowed'
                        : 'text-blue-400 hover:text-white hover:bg-blue-500/20'
                    }`}
                  >
                    + Add
                  </button>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function FantasyBuild() {
  const { matchId } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const [selected, setSelected] = useState([]) // ordered list of player_keys, max 11
  const [captain, setCaptain] = useState('')
  const [vc, setVc] = useState('')
  const [teamName, setTeamName] = useState('My Dream XI')
  const [search, setSearch] = useState('')
  const [deleteError, setDeleteError] = useState('')
  const [createError, setCreateError] = useState('')

  // ── Fetch squads — always fresh
  const { data: squadsData, isLoading: squadsLoading, error: squadsError } = useQuery({
    queryKey: ['squads', matchId],
    queryFn: async () => {
      const { data } = await api.get(`/matches/${matchId}/squads`)
      return data
    },
    staleTime: 0,
    refetchOnMount: 'always',
  })

  // ── Fetch my teams for this match — always fresh
  const { data: teamsData, isLoading: teamsLoading } = useQuery({
    queryKey: ['fantasy-teams', matchId],
    queryFn: async () => {
      const { data } = await api.get(`/matches/${matchId}/fantasy/teams`)
      return data
    },
    staleTime: 0,
    refetchOnMount: 'always',
  })

  const deleteMutation = useMutation({
    mutationFn: async (teamId) => api.delete(`/fantasy/teams/${teamId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['fantasy-teams', matchId] }),
    onError: err => setDeleteError(friendlyError(err)),
  })

  const createMutation = useMutation({
    mutationFn: ({ submit }) =>
      createTeam(matchId, teamName, selected, safeCapt, safeVc, submit),
    onSuccess: (team) => {
      qc.invalidateQueries({ queryKey: ['fantasy-teams', matchId] })
      navigate(`/fantasy/teams/${team.id}`)
    },
    onError: err => setCreateError(friendlyError(err)),
  })

  // ── Derived data ─────────────────────────────────────────────────────────────

  const squadByTeam = useMemo(() => {
    const raw = squadsData?.players ?? {}
    return Object.entries(raw).map(([teamName, players]) => ({
      teamName,
      players: (players ?? []),
    }))
  }, [squadsData])

  const allPlayers = useMemo(() => squadByTeam.flatMap(t => t.players), [squadByTeam])

  const selectedSet = useMemo(() => new Set(selected), [selected])
  const filledCount = selected.length

  // Guard: captain/vc must always be from current XI
  const safeCapt = selected.includes(captain) ? captain : ''
  const safeVc   = selected.includes(vc) ? vc : ''

  // Filtered players for search
  const filteredSquads = useMemo(() => {
    if (!search.trim()) return squadByTeam
    const q = search.toLowerCase()
    return squadByTeam.map(t => ({
      ...t,
      players: t.players.filter(p => p.player_key.toLowerCase().includes(q)),
    })).filter(t => t.players.length > 0)
  }, [squadByTeam, search])

  // ── Slot helpers ─────────────────────────────────────────────────────────────

  const addPlayer = (playerKey) => {
    if (selectedSet.has(playerKey)) return
    if (selected.length >= 11) return
    setSelected(prev => [...prev, playerKey])
  }

  const removePlayer = (playerKey) => {
    setSelected(prev => prev.filter(k => k !== playerKey))
    if (captain === playerKey) setCaptain('')
    if (vc === playerKey) setVc('')
  }

  const clearAll = () => {
    setSelected([])
    setCaptain('')
    setVc('')
  }

  const autoFill = () => {
    const needed = 11 - selected.length
    if (needed <= 0) return
    const additions = allPlayers
      .filter(p => !selectedSet.has(p.player_key))
      .slice(0, needed)
      .map(p => p.player_key)
    setSelected(prev => [...prev, ...additions])
  }

  // ── Validation ───────────────────────────────────────────────────────────────

  const canSaveDraft = filledCount > 0 && teamName.trim().length > 0
  const canSubmit    = filledCount === 11 && safeCapt && safeVc && safeCapt !== safeVc && teamName.trim().length > 0

  const existingTeams = teamsData?.teams ?? []

  if (squadsLoading || teamsLoading) return <PageSpinner />
  if (squadsError) return <ErrorCard error={squadsError} />

  const matchup = squadsData?.matchup || `Match ${matchId}`
  const matchDate = squadsData?.date || ''

  return (
    <div className="max-w-7xl mx-auto">
      {/* Breadcrumb */}
      <Link to="/fantasy" className="text-slate-400 hover:text-slate-200 text-sm inline-flex items-center gap-1 mb-4">
        ← Fantasy
      </Link>

      <div className="mb-5">
        <h1 className="page-header">Build Your XI</h1>
        <p className="page-sub">{matchup}{matchDate ? ` · ${matchDate}` : ''}</p>
      </div>

      {/* ── MY TEAMS ────────────────────────────────────────────────────────── */}
      {existingTeams.length > 0 && (
        <section className="card p-4 mb-6">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
            My Teams for this match
          </p>
          <div className="flex flex-col gap-2">
            {existingTeams.map(t => (
              <TeamRow
                key={t.id}
                team={t}
                onDelete={id => {
                  if (confirm('Delete this draft team?')) {
                    setDeleteError('')
                    deleteMutation.mutate(id)
                  }
                }}
                isDeleting={deleteMutation.isPending}
              />
            ))}
          </div>
          {deleteError && (
            <p className="text-red-400 text-xs mt-3 bg-red-500/10 border border-red-500/20 rounded px-3 py-2">
              {deleteError}
            </p>
          )}
        </section>
      )}

      {/* ── BUILD NEW TEAM ───────────────────────────────────────────────────── */}
      <div className="card p-4">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-5">
          {existingTeams.length > 0 ? 'Build Another Team' : 'Pick Your XI'}
        </p>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">

          {/* ── LEFT: Squad browser ─────────────────────────────────────────── */}
          <div className="flex flex-col gap-3">
            <p className="text-xs text-slate-500">
              Click <span className="text-blue-400">+ Add</span> to add a player to your XI
            </p>

            {/* Search */}
            <input
              className="input text-sm"
              placeholder="Search player…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />

            {/* Collapsible squad sections */}
            <div className="flex flex-col gap-2 max-h-[500px] overflow-y-auto pr-0.5">
              {filteredSquads.length === 0 && (
                <p className="text-slate-500 text-sm text-center py-8">No players found</p>
              )}
              {filteredSquads.map(({ teamName: tname, players }) => (
                <SquadSection
                  key={tname}
                  teamName={tname}
                  players={players}
                  selectedSet={selectedSet}
                  filledCount={filledCount}
                  onAdd={addPlayer}
                />
              ))}
            </div>
          </div>

          {/* ── RIGHT: My XI + C/VC + Submit ────────────────────────────────── */}
          <div className="flex flex-col gap-4">

            {/* Header row */}
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
                My XI
              </p>
              <div className="flex gap-3">
                <button
                  onClick={autoFill}
                  disabled={filledCount >= 11}
                  className="text-xs text-slate-400 hover:text-slate-200 disabled:opacity-40 transition-colors"
                >
                  Auto-fill
                </button>
                <button
                  onClick={clearAll}
                  disabled={filledCount === 0}
                  className="text-xs text-slate-400 hover:text-red-400 disabled:opacity-40 transition-colors"
                >
                  Clear all
                </button>
              </div>
            </div>

            {/* Progress bar */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-slate-500">Players selected</span>
                <span className={`text-xs font-mono font-bold ${filledCount === 11 ? 'text-emerald-400' : 'text-white'}`}>
                  {filledCount}/11
                </span>
              </div>
              <div className="h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-300 ${filledCount === 11 ? 'bg-emerald-500' : 'bg-blue-500'}`}
                  style={{ width: `${(filledCount / 11) * 100}%` }}
                />
              </div>
            </div>

            {/* 11 slots */}
            <div className="flex flex-col gap-1 min-h-[220px]">
              {Array.from({ length: 11 }, (_, i) => {
                const key = selected[i]
                return (
                  <div
                    key={i}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                      key ? 'bg-white/[0.04]' : 'bg-white/[0.02] border border-dashed border-white/[0.06]'
                    }`}
                  >
                    <span className="text-slate-600 font-mono text-xs w-4 shrink-0">{i + 1}</span>
                    {key ? (
                      <>
                        <span className="text-white flex-1 truncate">{key}</span>
                        {key === safeCapt && <span className="text-amber-400 text-xs font-bold shrink-0">C</span>}
                        {key === safeVc && <span className="text-blue-400 text-xs font-bold shrink-0">VC</span>}
                        <button
                          onClick={() => removePlayer(key)}
                          className="text-slate-600 hover:text-red-400 text-xs shrink-0 transition-colors ml-1"
                        >
                          ✕
                        </button>
                      </>
                    ) : (
                      <span className="text-slate-600 text-xs">Empty slot</span>
                    )}
                  </div>
                )
              })}
            </div>

            {/* Captain & Vice-captain */}
            <div className="border-t border-white/[0.07] pt-4 flex flex-col gap-3">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
                Captain & Vice-captain
              </p>
              <p className="text-xs text-slate-500">
                Captain scores <span className="text-amber-400">2×</span> points ·
                Vice-captain scores <span className="text-blue-400">1.5×</span> points · Must be different players
              </p>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-slate-400 mb-1.5">
                    Captain <span className="text-amber-400">(C)</span>
                  </label>
                  <select
                    className="select text-sm"
                    value={safeCapt}
                    onChange={e => { setCaptain(e.target.value); if (e.target.value === safeVc) setVc('') }}
                    disabled={filledCount === 0}
                  >
                    <option value="">Select captain</option>
                    {selected.map(k => (
                      <option key={k} value={k} disabled={k === safeVc}>{k}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1.5">
                    Vice-captain <span className="text-blue-400">(VC)</span>
                  </label>
                  <select
                    className="select text-sm"
                    value={safeVc}
                    onChange={e => { setVc(e.target.value); if (e.target.value === safeCapt) setCaptain('') }}
                    disabled={filledCount === 0}
                  >
                    <option value="">Select vice-captain</option>
                    {selected.map(k => (
                      <option key={k} value={k} disabled={k === safeCapt}>{k}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            {/* Team name */}
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">Team name</label>
              <input
                className="input text-sm"
                value={teamName}
                maxLength={40}
                onChange={e => setTeamName(e.target.value)}
                placeholder="My Dream XI"
              />
            </div>

            {/* Requirements checklist */}
            <div className="bg-white/[0.03] rounded-lg p-3 flex flex-col gap-1.5">
              {[
                { ok: filledCount === 11, label: `11 players selected (${filledCount}/11)` },
                { ok: !!safeCapt,         label: safeCapt ? `Captain: ${safeCapt}` : 'Captain not set' },
                { ok: !!safeVc,           label: safeVc ? `Vice-captain: ${safeVc}` : 'Vice-captain not set' },
                { ok: !!teamName.trim(),  label: 'Team has a name' },
              ].map(({ ok, label }, i) => (
                <p key={i} className={`text-xs flex items-center gap-2 ${ok ? 'text-emerald-400' : 'text-slate-500'}`}>
                  <span className="text-base leading-none">{ok ? '✓' : '○'}</span>
                  {label}
                </p>
              ))}
            </div>

            {/* Points note */}
            <p className="text-xs text-slate-500 bg-amber-500/5 border border-amber-500/10 rounded-lg px-3 py-2">
              Points are <span className="text-amber-400 font-medium">revealed only after you submit.</span>{' '}
              No stats are shown during team building.
            </p>

            {/* Error */}
            {createError && (
              <p className="text-red-400 text-xs bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                {createError}
              </p>
            )}

            {/* Action buttons */}
            <div className="flex gap-2">
              <button
                onClick={() => { setCreateError(''); createMutation.mutate({ submit: false }) }}
                disabled={!canSaveDraft || createMutation.isPending}
                className="btn-secondary"
              >
                {createMutation.isPending ? 'Saving…' : 'Save Draft'}
              </button>
              <button
                onClick={() => { setCreateError(''); createMutation.mutate({ submit: true }) }}
                disabled={!canSubmit || createMutation.isPending}
                className="btn-primary flex-1 justify-center"
              >
                {createMutation.isPending ? 'Submitting…' : 'Create & Submit →'}
              </button>
            </div>

            <p className="text-xs text-slate-600 text-center">
              Save Draft: you can set C/VC and submit later on the next screen
            </p>
          </div>

        </div>
      </div>
    </div>
  )
}
