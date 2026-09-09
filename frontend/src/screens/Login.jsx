import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { login } from '../api'
import { useAuth } from '../auth/AuthContext'

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
    <div className="max-w-sm mx-auto flex flex-col gap-5 p-6">
      <h1 className="text-2xl font-semibold">Sign in</h1>
      <form className="flex flex-col gap-4" onSubmit={onSubmit}>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Email
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                 className="rounded-lg border border-gray-300 p-2 font-normal" />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Password
          <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
                 className="rounded-lg border border-gray-300 p-2 font-normal" />
        </label>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button type="submit" disabled={busy}
                className="rounded-lg bg-purple-600 text-white py-2 font-medium disabled:opacity-50">
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      <p className="text-sm text-gray-600">
        No account? <Link to="/signup" className="underline">Create one</Link>
      </p>
    </div>
  )
}
