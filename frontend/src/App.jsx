import { useEffect, useState } from 'react'
import { Link, Navigate, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import { getReport, pollReport, rescoreAttempt } from './api'
import { AuthProvider, useAuth } from './auth/AuthContext'
import RequireAuth from './auth/RequireAuth'
import AppShell from './components/AppShell'
import CandidateFlow from './flows/CandidateFlow'
import Admin from './screens/Admin'
import Analytics from './screens/Analytics'
import Landing from './screens/Landing'
import Login from './screens/Login'
import Profile from './screens/Profile'
import PasswordRecovery from './screens/PasswordRecovery'
import Recruiter from './screens/Recruiter'
import Report from './screens/Report'
import Results from './screens/Results'
import Signup from './screens/Signup'

function RoleHome() {
  const { has, user } = useAuth()
  if (has('roles.manage')) return <Navigate to="/admin" replace />
  if (has('candidates.view')) return <Navigate to="/dashboard" replace />
  return <Navigate to={user?.profile ? '/results' : '/profile'} replace />
}

function Home() {
  const { user, loading } = useAuth()
  if (loading) return null
  return user ? <RoleHome /> : <Landing />
}

function ReportRoute() {
  const { attemptId } = useParams()
  const { has } = useAuth()
  const [report, setReport] = useState(null)
  const [err, setErr] = useState(false)
  const [rescoreBusy, setRescoreBusy] = useState(false)
  const [rescoreError, setRescoreError] = useState(null)
  const recruiterView = has('candidates.view')
  useEffect(() => {
    getReport(attemptId).then(setReport).catch(() => setErr(true))
  }, [attemptId])
  // A failed re-score must not tear down the report we already have: keep it
  // on screen and explain inline, so the button can simply be pressed again.
  const rescore = async () => {
    if (rescoreBusy) return
    setRescoreBusy(true)
    setRescoreError(null)
    try {
      await rescoreAttempt(attemptId)
    } catch {
      setRescoreError('Could not start re-scoring. It may already be running, or the attempt is no longer in a failed state.')
      setRescoreBusy(false)
      return
    }
    try {
      setReport(await pollReport(attemptId))
    } catch {
      setRescoreError('Re-scoring is still running. Refresh this page in a minute.')
    } finally {
      setRescoreBusy(false)
    }
  }
  return (
    <div className="max-w-3xl mx-auto px-6 py-8 flex flex-col gap-6">
      <Link
        to={recruiterView ? '/dashboard' : '/results'}
        className="self-start text-sm font-medium text-blue-700 hover:underline"
      >
        Back to {recruiterView ? 'candidates' : 'my results'}
      </Link>
      {err && <p className="text-center text-red-600">Report not available.</p>}
      {!err && !report && <p className="text-center text-gray-500">Loading…</p>}
      {report && (
        <Report
          report={report}
          onRescore={recruiterView ? rescore : undefined}
          rescoreBusy={rescoreBusy}
          rescoreError={rescoreError}
        />
      )}
    </div>
  )
}

function Dashboard() {
  const navigate = useNavigate()
  return <Recruiter onOpenReport={(attemptId) => navigate(`/report/${attemptId}`)} />
}

function RecruiterPreview({ analytics = false }) {
  const navigate = useNavigate()
  return analytics ? <Analytics /> : <Recruiter onOpenReport={(attemptId) => navigate(`/report/${attemptId}`)} />
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/forgot-password" element={<PasswordRecovery />} />
      <Route path="/profile" element={<RequireAuth permission="test.take"><AppShell><Profile /></AppShell></RequireAuth>} />
      <Route path="/results" element={<RequireAuth permission="test.take"><AppShell><Results /></AppShell></RequireAuth>} />
      <Route path="/test" element={<RequireAuth permission="test.take"><AppShell><CandidateFlow /></AppShell></RequireAuth>} />
      <Route path="/report/:attemptId" element={<RequireAuth><AppShell><ReportRoute /></AppShell></RequireAuth>} />
      <Route path="/dashboard" element={<RequireAuth permission="candidates.view"><AppShell><Dashboard /></AppShell></RequireAuth>} />
      <Route path="/analytics" element={<RequireAuth permission="analytics.view"><AppShell><Analytics /></AppShell></RequireAuth>} />
      <Route path="/admin" element={<RequireAuth permission="roles.manage"><AppShell><Admin /></AppShell></RequireAuth>} />
      <Route path="/recruiter-preview" element={<RequireAuth permission="roles.manage"><AppShell recruiterPreview><RecruiterPreview /></AppShell></RequireAuth>} />
      <Route path="/recruiter-preview/analytics" element={<RequireAuth permission="roles.manage"><AppShell recruiterPreview><RecruiterPreview analytics /></AppShell></RequireAuth>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}
