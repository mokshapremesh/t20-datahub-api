import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import RequireAuth from './components/RequireAuth'
import RequireAdmin from './components/RequireAdmin'

import Login from './pages/Login'
import Register from './pages/Register'
import Matches from './pages/Matches'
import MatchDetail from './pages/MatchDetail'
import Scorecard from './pages/Scorecard'
import Squads from './pages/Squads'
import Profile from './pages/Profile'
import Dashboard from './pages/Dashboard'
import Fantasy from './pages/Fantasy'
import FantasyBuild from './pages/FantasyBuild'
import FantasyTeamDetail from './pages/FantasyTeamDetail'
import MatchLeaderboard from './pages/MatchLeaderboard'
import GlobalLeaderboard from './pages/GlobalLeaderboard'
import AdminMatches from './pages/AdminMatches'
import NotFound from './pages/NotFound'

export default function App() {
  return (
    <Routes>
      {/* Auth pages — full screen, no navbar */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      <Route element={<Layout />}>
        <Route index element={<Navigate to="/matches" replace />} />

        {/* Matches — discovery & scorecards */}
        <Route path="/matches" element={<Matches />} />
        <Route path="/matches/:matchId" element={<MatchDetail />} />
        <Route path="/matches/:matchId/scorecard" element={<Scorecard />} />
        <Route path="/matches/:matchId/squads" element={<Squads />} />

        {/* Fantasy — top-level section (public) */}
        <Route path="/fantasy" element={<Fantasy />} />
        <Route path="/fantasy/leaderboard" element={<GlobalLeaderboard />} />
        <Route path="/fantasy/matches/:matchId/leaderboard" element={<MatchLeaderboard />} />

        {/* Legacy leaderboard URL — still works */}
        <Route path="/matches/:matchId/fantasy/leaderboard" element={<MatchLeaderboard />} />

        {/* Fantasy — auth-gated */}
        <Route element={<RequireAuth />}>
          <Route path="/fantasy/matches/:matchId/build" element={<FantasyBuild />} />
          <Route path="/fantasy/teams/:teamId" element={<FantasyTeamDetail />} />
          <Route path="/me/profile" element={<Profile />} />
          <Route path="/me/dashboard" element={<Dashboard />} />
        </Route>

        {/* Admin */}
        <Route element={<RequireAdmin />}>
          <Route path="/admin/matches" element={<AdminMatches />} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
