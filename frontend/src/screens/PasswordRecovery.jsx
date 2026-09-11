import { Link } from 'react-router-dom'
import { useState } from 'react'
import { requestPasswordReset } from '../api'
import AuthLayout from '../components/AuthLayout'

const inputClass = 'w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-blue-700 focus:ring-2 focus:ring-blue-100'

export default function PasswordRecovery() {
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setError(null)
    try { setMessage((await requestPasswordReset({ email })).message) }
    catch (err) { setError(err.status === 429 ? 'Too many requests. Please try again later.' : 'Enter a valid email address.') }
    finally { setBusy(false) }
  }
  return <AuthLayout title="Recover your password" subtitle="Send a request and an administrator will help you regain access." footer="For security, we do not confirm whether an account exists.">
    {message ? <div className="flex flex-col gap-5"><p role="status" className="rounded-lg bg-green-50 p-3 text-sm text-green-800">{message}</p><Link to="/login" className="text-sm font-medium text-blue-700 hover:underline">Return to sign in</Link></div> : <form className="flex flex-col gap-5" onSubmit={submit} noValidate><div><label htmlFor="recovery-email" className="block text-sm font-medium mb-1.5">Email</label><input id="recovery-email" className={inputClass} type="email" required autoComplete="email" autoFocus value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" /></div>{error && <p role="alert" className="text-sm text-red-600">{error}</p>}<button type="submit" disabled={busy} className="w-full rounded-lg bg-blue-700 text-white py-2.5 font-medium hover:bg-blue-800 disabled:opacity-50">{busy ? 'Sending request…' : 'Request help'}</button></form>}
    <div className="mt-6 border-t border-gray-200 pt-5 text-sm text-gray-600"><Link to="/login" className="font-medium text-blue-700 hover:underline">Back to sign in</Link></div>
  </AuthLayout>
}
