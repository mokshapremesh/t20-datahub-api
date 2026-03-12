import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { PageSpinner } from '../components/Spinner'
import ErrorCard from '../components/ErrorCard'
import EmptyState from '../components/EmptyState'

const EMPTY_FORM = {
  team1: '', team2: '', match_date: '', venue: '', stage: '', tournament_year: '',
  toss_winner: '', toss_decision: 'bat', winner: '',
}

function MatchForm({ initial = EMPTY_FORM, onSubmit, onCancel, isPending, error }) {
  const [form, setForm] = useState(initial)
  const f = key => ({ value: form[key], onChange: e => setForm(p => ({ ...p, [key]: e.target.value })) })

  return (
    <form onSubmit={e => { e.preventDefault(); onSubmit(form) }} className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-slate-400 mb-1">Team 1 *</label>
          <input className="input" placeholder="India" required {...f('team1')} />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Team 2 *</label>
          <input className="input" placeholder="Pakistan" required {...f('team2')} />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Date *</label>
          <input className="input" type="date" required {...f('match_date')} />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Year *</label>
          <input className="input" placeholder="2024" required {...f('tournament_year')} />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Stage</label>
          <input className="input" placeholder="Super 8" {...f('stage')} />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Venue</label>
          <input className="input" placeholder="MCG" {...f('venue')} />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Winner</label>
          <input className="input" placeholder="India" {...f('winner')} />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Toss winner</label>
          <input className="input" placeholder="India" {...f('toss_winner')} />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Toss decision</label>
          <select className="select" {...f('toss_decision')}>
            <option value="bat">Bat</option>
            <option value="field">Field</option>
          </select>
        </div>
      </div>

      {error && (
        <p className="text-red-400 text-xs bg-red-500/10 border border-red-500/20 rounded px-3 py-2">
          {error?.response?.data?.detail || 'An error occurred'}
        </p>
      )}

      <div className="flex gap-2 mt-1">
        <button type="submit" disabled={isPending} className="btn-primary">
          {isPending ? <><span className="spinner w-4 h-4" /> Saving…</> : 'Save'}
        </button>
        <button type="button" onClick={onCancel} className="btn-secondary">Cancel</button>
      </div>
    </form>
  )
}

export default function AdminMatches() {
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [editId, setEditId] = useState(null)

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['admin-matches'],
    queryFn: async () => {
      const r = await api.get('/matches')
      return r.data
    },
  })

  const createMutation = useMutation({
    mutationFn: async form => {
      const body = Object.fromEntries(Object.entries(form).filter(([, v]) => v))
      const r = await api.post('/matches', body)
      return r.data
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin-matches'] }); setShowCreate(false) },
  })

  const updateMutation = useMutation({
    mutationFn: async ({ id, form }) => {
      const body = Object.fromEntries(Object.entries(form).filter(([, v]) => v))
      const r = await api.patch(`/matches/${id}`, body)
      return r.data
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin-matches'] }); setEditId(null) },
  })

  const deleteMutation = useMutation({
    mutationFn: async id => { await api.delete(`/matches/${id}`) },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-matches'] }),
  })

  const matches = data?.matches || []

  if (isLoading) return <PageSpinner />
  if (error) return <ErrorCard error={error} retry={refetch} />

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="page-header">⚙️ Admin — Matches</h1>
          <p className="page-sub">{matches.length} total matches</p>
        </div>
        <button onClick={() => setShowCreate(v => !v)} className="btn-primary">
          + New Match
        </button>
      </div>

      {showCreate && (
        <div className="card p-5 mb-5">
          <h3 className="font-semibold text-white mb-4">Create match</h3>
          <MatchForm
            onSubmit={form => createMutation.mutate(form)}
            onCancel={() => setShowCreate(false)}
            isPending={createMutation.isPending}
            error={createMutation.error}
          />
        </div>
      )}

      {matches.length === 0 ? (
        <EmptyState icon="🏏" title="No matches" subtitle="Create the first match above" />
      ) : (
        <div className="card overflow-hidden">
          <table className="table-base w-full">
            <thead>
              <tr>
                <th>ID</th>
                <th>Match</th>
                <th>Year</th>
                <th>Stage</th>
                <th>Winner</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {matches.map(m => (
                <>
                  <tr key={m.id}>
                    <td className="font-mono text-slate-500 text-xs">{m.id}</td>
                    <td>
                      <span className="text-slate-200 font-medium">{m.team1}</span>
                      <span className="text-slate-500 mx-1">vs</span>
                      <span className="text-slate-200 font-medium">{m.team2}</span>
                    </td>
                    <td className="text-slate-400">{m.tournament_year}</td>
                    <td className="text-slate-400 text-sm">{m.stage}</td>
                    <td className="text-emerald-400 text-sm">{m.winner || '—'}</td>
                    <td>
                      <div className="flex gap-1">
                        <button
                          onClick={() => setEditId(editId === m.id ? null : m.id)}
                          className="text-xs px-2 py-1 rounded text-slate-400 hover:text-white hover:bg-white/[0.06] transition-colors"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => { if (confirm(`Delete ${m.team1} vs ${m.team2}?`)) deleteMutation.mutate(m.id) }}
                          className="text-xs px-2 py-1 rounded text-red-400/60 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                  {editId === m.id && (
                    <tr key={`edit-${m.id}`}>
                      <td colSpan={6} className="p-4 bg-white/[0.02]">
                        <MatchForm
                          initial={{
                            team1: m.team1 || '',
                            team2: m.team2 || '',
                            match_date: m.match_date || '',
                            venue: m.venue || '',
                            stage: m.stage || '',
                            tournament_year: m.tournament_year || '',
                            toss_winner: m.toss_winner || '',
                            toss_decision: m.toss_decision || 'bat',
                            winner: m.winner || '',
                          }}
                          onSubmit={form => updateMutation.mutate({ id: m.id, form })}
                          onCancel={() => setEditId(null)}
                          isPending={updateMutation.isPending}
                          error={updateMutation.error}
                        />
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
