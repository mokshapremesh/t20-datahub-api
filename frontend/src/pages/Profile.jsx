import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import api from '../api/client'
import { PageSpinner } from '../components/Spinner'
import ErrorCard from '../components/ErrorCard'

function AdminPromotion() {
  const [secret, setSecret] = useState('')
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')

  const mut = useMutation({
    mutationFn: async () => {
      const { data } = await api.post(`/auth/make-admin?secret=${encodeURIComponent(secret)}`)
      return data
    },
    onSuccess: (data) => { setMsg(data.message); setErr('') },
    onError: (e) => { setErr(e?.response?.data?.detail || 'Failed'); setMsg('') },
  })

  return (
    <div className="mt-4 card p-4">
      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Admin Access</p>
      <div className="flex gap-2">
        <input
          className="input text-sm flex-1"
          type="password"
          placeholder="Admin secret key"
          value={secret}
          onChange={e => setSecret(e.target.value)}
        />
        <button
          onClick={() => mut.mutate()}
          disabled={!secret || mut.isPending}
          className="btn-secondary text-xs shrink-0"
        >
          {mut.isPending ? 'Promoting…' : 'Make me admin'}
        </button>
      </div>
      {msg && <p className="text-emerald-400 text-xs mt-2">✓ {msg}</p>}
      {err && <p className="text-red-400 text-xs mt-2">{err}</p>}
      {msg && <p className="text-slate-500 text-xs mt-1">Log out and back in for admin panel to appear.</p>}
    </div>
  )
}

export default function Profile() {
  const qc = useQueryClient()

  const { data: profileData, isLoading, error, refetch } = useQuery({
    queryKey: ['profile'],
    queryFn: async () => {
      const r = await api.get('/me/profile')
      return r.data
    },
  })

  const { data: teamsData } = useQuery({
    queryKey: ['options-teams'],
    queryFn: async () => {
      const r = await api.get('/options/teams')
      return r.data
    },
  })

  const [form, setForm] = useState({ display_name: '', fav_team: '', fav_player_key: '', fav_year: '' })
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (profileData?.display_name !== undefined) {
      setForm({
        display_name: profileData.display_name || '',
        fav_team: profileData.fav_team?.key || '',
        fav_player_key: profileData.fav_player?.key || '',
        fav_year: profileData.fav_year || '',
      })
    }
  }, [profileData])

  const saveMutation = useMutation({
    mutationFn: async () => {
      const params = new URLSearchParams()
      if (form.display_name) params.append('display_name', form.display_name)
      if (form.fav_team) params.append('fav_team', form.fav_team)
      if (form.fav_player_key) params.append('fav_player_key', form.fav_player_key)
      if (form.fav_year) params.append('fav_year', form.fav_year)
      const r = await api.put(`/me/profile?${params.toString()}`)
      return r.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['profile'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async () => {
      await api.delete('/me/profile')
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['profile'] })
      setForm({ display_name: '', fav_team: '', fav_player_key: '', fav_year: '' })
    },
  })

  const { data: yearsData } = useQuery({
    queryKey: ['options-years'],
    queryFn: async () => { const r = await api.get('/options/years'); return r.data },
    staleTime: Infinity,
  })

  const teams = teamsData?.teams || []
  const years = yearsData?.years ?? []

  if (isLoading) return <PageSpinner />
  if (error && error?.response?.status !== 404) return <ErrorCard error={error} retry={refetch} />

  const hasProfile = profileData?.display_name !== undefined

  return (
    <div className="max-w-xl mx-auto">
      <div className="mb-6">
        <h1 className="page-header">Fan Profile</h1>
        <p className="page-sub">Set your favourites to unlock your personalised dashboard</p>
      </div>

      <div className="card p-6">
        <form
          onSubmit={e => { e.preventDefault(); saveMutation.mutate() }}
          className="flex flex-col gap-5"
        >
          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-1.5">Display Name</label>
            <input
              className="input"
              placeholder="e.g. Cricket Fan 🏏"
              value={form.display_name}
              onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))}
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-1.5">Favourite Team</label>
            <select
              className="select"
              value={form.fav_team}
              onChange={e => setForm(f => ({ ...f, fav_team: e.target.value }))}
            >
              <option value="">Select a team</option>
              {teams.map(t => (
                <option key={t.team_key} value={t.team_key}>{t.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-1.5">Favourite Player Key</label>
            <input
              className="input"
              placeholder="e.g. V Kohli (exact player key)"
              value={form.fav_player_key}
              onChange={e => setForm(f => ({ ...f, fav_player_key: e.target.value }))}
            />
            <p className="text-slate-500 text-xs mt-1">
              Use the exact key from{' '}
              <a href="/api/options/players" target="_blank" className="text-emerald-400 hover:underline">
                /options/players
              </a>
            </p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-1.5">Favourite Tournament Year</label>
            <select
              className="select"
              value={form.fav_year}
              onChange={e => setForm(f => ({ ...f, fav_year: e.target.value }))}
            >
              <option value="">Select a year</option>
              {years.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>

          {saveMutation.error && (
            <p className="text-red-400 text-xs bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              {saveMutation.error?.response?.data?.detail || 'Save failed'}
            </p>
          )}

          {saved && (
            <p className="text-emerald-400 text-xs bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">
              ✓ Profile saved
            </p>
          )}

          <div className="flex gap-3">
            <button
              type="submit"
              disabled={saveMutation.isPending}
              className="btn-primary"
            >
              {saveMutation.isPending ? <><span className="spinner w-4 h-4" /> Saving…</> : 'Save profile'}
            </button>

            {hasProfile && (
              <button
                type="button"
                onClick={() => { if (confirm('Delete your profile?')) deleteMutation.mutate() }}
                disabled={deleteMutation.isPending}
                className="btn-danger"
              >
                Delete
              </button>
            )}
          </div>
        </form>
      </div>

      {hasProfile && (
        <div className="mt-4 card p-4 flex items-center justify-between">
          <div>
            <p className="font-medium text-white text-sm">View your analytics dashboard</p>
            <p className="text-slate-400 text-xs">Personalised to your favourites</p>
          </div>
          <Link to="/me/dashboard" className="btn-primary text-xs py-1.5">
            Dashboard →
          </Link>
        </div>
      )}

      <AdminPromotion />
    </div>
  )
}
