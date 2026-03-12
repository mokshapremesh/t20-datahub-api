import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { PageSpinner } from '../components/Spinner'
import ErrorCard from '../components/ErrorCard'
import EmptyState from '../components/EmptyState'

function StatusBadge({ status }) {
  if (status === 'SUBMITTED') {
    return <span className="badge bg-emerald-500/20 text-emerald-400">Submitted</span>
  }
  return <span className="badge bg-amber-500/20 text-amber-400">Draft</span>
}

function TeamCard({ team, matchId, onDelete }) {
  return (
    <div className="card p-4 hover:border-white/[0.14] transition-colors">
      <div className="flex items-start justify-between gap-2 mb-3">
        <div>
          <h3 className="font-bold text-white">{team.name}</h3>
          <div className="flex items-center gap-2 mt-1">
            <StatusBadge status={team.status} />
            {team.total_points !== null && team.total_points !== undefined && (
              <span className="text-amber-400 font-mono text-sm font-bold">
                {team.total_points} pts
              </span>
            )}
          </div>
        </div>
        <div className="text-right text-xs text-slate-500">
          {team.requirements.current_players}/11 players
        </div>
      </div>

      {/* Players preview */}
      <div className="flex flex-wrap gap-1 mb-3">
        {team.player_keys?.slice(0, 6).map(p => (
          <span key={p} className={`text-xs px-2 py-0.5 rounded-full ${
            p === team.captain_key
              ? 'bg-amber-500/20 text-amber-300'
              : p === team.vice_captain_key
              ? 'bg-blue-500/20 text-blue-300'
              : 'bg-white/[0.06] text-slate-400'
          }`}>
            {p === team.captain_key ? '(C) ' : p === team.vice_captain_key ? '(VC) ' : ''}
            {p}
          </span>
        ))}
        {(team.player_keys?.length || 0) > 6 && (
          <span className="text-xs text-slate-500 px-2 py-0.5">
            +{team.player_keys.length - 6} more
          </span>
        )}
      </div>

      <div className="flex gap-2">
        {team.status === 'DRAFT' && (
          <Link
            to={`/fantasy/teams/${team.id}`}
            className="btn-primary text-xs py-1.5"
          >
            ✏️ Edit team
          </Link>
        )}
        {team.status === 'SUBMITTED' && (
          <Link
            to={`/fantasy/teams/${team.id}`}
            className="btn-secondary text-xs py-1.5"
          >
            👁 View
          </Link>
        )}
        <Link
          to={`/matches/${matchId}/fantasy/leaderboard`}
          className="btn-secondary text-xs py-1.5"
        >
          🏅 Leaderboard
        </Link>
        {team.status === 'DRAFT' && (
          <button
            onClick={() => onDelete(team.id)}
            className="text-xs px-2.5 py-1 rounded text-red-400/70 hover:text-red-400 hover:bg-red-500/10 transition-colors"
          >
            Delete
          </button>
        )}
      </div>
    </div>
  )
}

export default function FantasyTeams() {
  const { matchId } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [teamName, setTeamName] = useState('')

  const { data: squadsData } = useQuery({
    queryKey: ['squads', matchId],
    queryFn: async () => {
      const r = await api.get(`/matches/${matchId}/squads`)
      return r.data
    },
  })

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['fantasy-teams', matchId],
    queryFn: async () => {
      const r = await api.get(`/matches/${matchId}/fantasy/teams`)
      return r.data
    },
  })

  const createMutation = useMutation({
    mutationFn: async (name) => {
      const r = await api.post(`/matches/${matchId}/fantasy/teams`, null, {
        params: { name },
      })
      return r.data
    },
    onSuccess: (team) => {
      qc.invalidateQueries({ queryKey: ['fantasy-teams', matchId] })
      navigate(`/fantasy/teams/${team.id}`)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (teamId) => {
      await api.delete(`/fantasy/teams/${teamId}`)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fantasy-teams', matchId] })
    },
  })

  const matchup = squadsData?.matchup || `Match ${matchId}`
  const teams = data?.teams || []

  if (isLoading) return <PageSpinner />
  if (error) return <ErrorCard error={error} retry={refetch} />

  return (
    <div className="max-w-3xl mx-auto">
      <Link to={`/matches/${matchId}`} className="text-slate-400 hover:text-slate-200 text-sm inline-flex items-center gap-1 mb-4">
        ← {matchup}
      </Link>

      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="page-header">My Fantasy Teams</h1>
          <p className="page-sub">{matchup}</p>
        </div>
        <button
          onClick={() => setShowCreate(v => !v)}
          className="btn-primary"
        >
          ✨ New Team
        </button>
      </div>

      {/* Create team panel */}
      {showCreate && (
        <div className="card p-5 mb-5">
          <h3 className="font-semibold text-white mb-3">Create new team</h3>
          <form
            onSubmit={e => {
              e.preventDefault()
              if (teamName.trim()) createMutation.mutate(teamName.trim())
            }}
            className="flex gap-2"
          >
            <input
              className="input flex-1"
              placeholder="Team name e.g. Dream XI"
              value={teamName}
              onChange={e => setTeamName(e.target.value)}
              required
            />
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="btn-primary shrink-0"
            >
              {createMutation.isPending ? <span className="spinner w-4 h-4" /> : 'Create'}
            </button>
          </form>
          {createMutation.error && (
            <p className="text-red-400 text-xs mt-2">
              {createMutation.error?.response?.data?.detail || 'Failed to create team'}
            </p>
          )}
          <p className="text-slate-500 text-xs mt-2">
            You'll pick players and set captain on the next screen.
          </p>
        </div>
      )}

      {/* Teams list */}
      {teams.length === 0 ? (
        <EmptyState
          icon="✨"
          title="No teams yet"
          subtitle="Create your first fantasy XI for this match"
          action={
            <button onClick={() => setShowCreate(true)} className="btn-primary">
              Build your XI
            </button>
          }
        />
      ) : (
        <div className="flex flex-col gap-4">
          {teams.map(t => (
            <TeamCard
              key={t.id}
              team={t}
              matchId={matchId}
              onDelete={id => { if (confirm('Delete this team?')) deleteMutation.mutate(id) }}
            />
          ))}
        </div>
      )}
    </div>
  )
}
