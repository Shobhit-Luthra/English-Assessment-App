import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { login } from '../api'
import { useAuth } from '../auth/AuthContext'
import AuthLayout from '../components/AuthLayout'

const inputClass =
  'w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none ' +
  'focus:border-blue-700 focus:ring-2 focus:ring-blue-100'

export default function Login() {
  const { user, refresh } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/" replace />

  const onSubmit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login({ email, password })
      await refresh()
      navigate(location.state?.from ?? '/', { replace: true })
    } catch (err) {
      setError(
        err.status === 429
          ? 'Too many attempts, try again shortly'
          : 'Invalid email or password',
      )
      setBusy(false)
    }
  }

  return (
    <AuthLayout
      title="Sign in"
      subtitle="Welcome back. Sign in to continue."
      footer="Sessions are encrypted and expire automatically."
    >
      <form className="flex flex-col gap-5" onSubmit={onSubmit} noValidate>
        <div>
          <label htmlFor="email" className="block text-sm font-medium mb-1.5">
            Email
          </label>
          <input
            id="email" type="email" required value={email}
            onChange={(e) => setEmail(e.target.value)} className={inputClass}
            autoComplete="email" autoFocus placeholder="you@example.com"
          />
        </div>
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label htmlFor="password" className="text-sm font-medium">Password</label>
            <Link to="/forgot-password" className="text-xs font-medium text-blue-700 hover:underline">Forgot password?</Link>
          </div>
          <input
            id="password" type="password" required value={password}
            onChange={(e) => setPassword(e.target.value)} className={inputClass}
            autoComplete="current-password" placeholder="••••••••"
          />
        </div>
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        <button type="submit" disabled={busy}
                className="w-full rounded-lg bg-blue-700 text-white py-2.5 font-medium hover:bg-blue-800 disabled:opacity-50">
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      <div className="mt-6 border-t border-gray-200 pt-5 text-sm text-gray-600">
        No account yet?
        <Link to="/signup" className="ml-1 font-medium text-blue-700 hover:underline">
          Create one
        </Link>
      </div>
    </AuthLayout>
  )
}
