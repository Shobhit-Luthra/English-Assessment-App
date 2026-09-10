import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { signup } from '../api'
import { useAuth } from '../auth/AuthContext'
import AuthLayout from '../components/AuthLayout'

const inputClass =
  'w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none ' +
  'focus:border-blue-700 focus:ring-2 focus:ring-blue-100'

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
    <AuthLayout
      title="Create your account"
      subtitle="Start your assessment in under a minute."
      footer="Protected by role-based access control."
    >
      <form className="flex flex-col gap-5" onSubmit={onSubmit} noValidate>
        <div>
          <label htmlFor="name" className="block text-sm font-medium mb-1.5">
            Full name
          </label>
          <input id="name" type="text" required value={form.display_name} onChange={set('display_name')}
                 className={inputClass} autoComplete="name" placeholder="Jane Doe" />
        </div>
        <div>
          <label htmlFor="email" className="block text-sm font-medium mb-1.5">
            Email
          </label>
          <input id="email" type="email" required value={form.email} onChange={set('email')}
                 className={inputClass} autoComplete="email" placeholder="you@example.com" />
        </div>
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label htmlFor="password" className="text-sm font-medium">Password</label>
            <span className="text-xs text-gray-400">at least 10 characters</span>
          </div>
          <input id="password" type="password" required minLength={10} value={form.password} onChange={set('password')}
                 className={inputClass} autoComplete="new-password" placeholder="••••••••••" />
        </div>
        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
            {error.startsWith('This email') && (
              <Link to="/login" className="ml-1 font-medium underline">Sign in instead</Link>
            )}
          </p>
        )}
        <button type="submit" disabled={busy}
                className="w-full rounded-lg bg-blue-700 text-white py-2.5 font-medium hover:bg-blue-800 disabled:opacity-50">
          {busy ? 'Creating…' : 'Create account'}
        </button>
      </form>
      <div className="mt-6 border-t border-gray-200 pt-5 text-sm text-gray-600">
        Already registered?
        <Link to="/login" className="ml-1 font-medium text-blue-700 hover:underline">
          Sign in
        </Link>
      </div>
      <p className="mt-6 text-xs text-gray-400 leading-relaxed">
        New accounts start with a candidate profile. Recruiter and administrator
        accounts are created by an admin.
      </p>
    </AuthLayout>
  )
}