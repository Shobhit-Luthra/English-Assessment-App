import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { putProfile } from '../api'
import { useAuth } from '../auth/AuthContext'

const inputClass =
  'w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none ' +
  'focus:border-blue-700 focus:ring-2 focus:ring-blue-100'

export default function Profile() {
  const { user, refresh } = useAuth()
  const navigate = useNavigate()
  const p = user?.profile ?? {}
  const name = user?.profile?.full_name || user?.display_name
  const [form, setForm] = useState({
    full_name: p.full_name ?? user?.display_name ?? '',
    phone: p.phone ?? '',
    city: p.city ?? '',
    first_language: p.first_language ?? '',
  })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const onSubmit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await putProfile({
        full_name: form.full_name.trim(),
        phone: form.phone.trim(),
        city: form.city.trim() || null,
        first_language: form.first_language.trim() || null,
      })
      await refresh()
      navigate('/test', { replace: true })
    } catch {
      setError('Could not save your details. Try again.')
      setBusy(false)
    }
  }

  return (
    <main className="py-10">
      <div className="max-w-md mx-auto px-6">
        <h1 className="text-2xl font-semibold">Your details</h1>
        <p className="text-sm text-gray-600 mt-1">
          {name ? `Welcome, ${name}. ` : ''}We use this to label your results.
          As soon as you save, you'll check your microphone and start the test.
        </p>
        <form className="flex flex-col gap-5 mt-8" onSubmit={onSubmit}>
          <div>
            <label htmlFor="full_name" className="block text-sm font-medium mb-1.5">
              Full name
            </label>
            <input id="full_name" type="text" required value={form.full_name} onChange={set('full_name')}
                   className={inputClass} autoComplete="name" />
          </div>
          <div>
            <label htmlFor="phone" className="block text-sm font-medium mb-1.5">
              Phone
            </label>
            <input id="phone" type="tel" required value={form.phone} onChange={set('phone')}
                   className={inputClass} autoComplete="tel" />
          </div>
          <div>
            <label htmlFor="city" className="block text-sm font-medium mb-1.5">
              City <span className="font-normal text-gray-400">(optional)</span>
            </label>
            <input id="city" type="text" value={form.city} onChange={set('city')}
                   className={inputClass} autoComplete="address-level2" />
          </div>
          <div>
            <label htmlFor="first_language" className="block text-sm font-medium mb-1.5">
              First language <span className="font-normal text-gray-400">(optional)</span>
            </label>
            <input id="first_language" type="text" value={form.first_language} onChange={set('first_language')}
                   className={inputClass} />
          </div>
          {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
          <button type="submit" disabled={busy}
                  className="rounded-lg bg-blue-700 text-white py-2.5 font-medium hover:bg-blue-800 disabled:opacity-50">
            {busy ? 'Saving…' : 'Save and continue'}
          </button>
        </form>
      </div>
    </main>
  )
}