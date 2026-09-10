import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { signup } from '../api'
import { useAuth } from '../auth/AuthContext'

export default function Signup() {
  const { user, refresh } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ email: '', display_name: '', password: '' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/" replace />
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const onSubmit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await signup(form)
      await refresh()
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.status === 409
        ? 'This email is already registered'
        : 'Could not create your account. Check the form and try again.')
      setBusy(false)
    }
  }

  return (
    <div className="max-w-sm mx-auto flex flex-col gap-5 p-6">
      <h1 className="text-2xl font-semibold">Create your account</h1>
      <form className="flex flex-col gap-4" onSubmit={onSubmit}>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Email
          <input type="email" required value={form.email} onChange={set('email')}
                 className="rounded-lg border border-gray-300 p-2 font-normal" />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Full name
          <input type="text" required value={form.display_name} onChange={set('display_name')}
                 className="rounded-lg border border-gray-300 p-2 font-normal" />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Password <span className="font-normal text-gray-500">(at least 10 characters)</span>
          <input type="password" required minLength={10} value={form.password} onChange={set('password')}
                 className="rounded-lg border border-gray-300 p-2 font-normal" />
        </label>
        {error && (
          <p className="text-sm text-red-600">
            {error}{' '}
            {error.startsWith('This email') && <Link to="/login" className="underline">Sign in</Link>}
          </p>
        )}
        <button type="submit" disabled={busy}
                className="rounded-lg bg-purple-600 text-white py-2 font-medium disabled:opacity-50">
          {busy ? 'Creating…' : 'Create account'}
        </button>
      </form>
      <p className="text-sm text-gray-600">
        Already registered? <Link to="/login" className="underline">Sign in</Link>
      </p>
    </div>
  )
}
