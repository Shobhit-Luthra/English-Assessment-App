import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { putProfile } from '../api'
import { useAuth } from '../auth/AuthContext'

export default function Profile() {
  const { user, refresh } = useAuth()
  const navigate = useNavigate()
  const p = user?.profile ?? {}
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
    <div className="max-w-md mx-auto flex flex-col gap-5 p-6">
      <h1 className="text-2xl font-semibold">Your details</h1>
      <p className="text-sm text-gray-600">We use this to label your results. It takes a moment.</p>
      <form className="flex flex-col gap-4" onSubmit={onSubmit}>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Full name
          <input required value={form.full_name} onChange={set('full_name')}
                 className="rounded-lg border border-gray-300 p-2 font-normal" />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Phone
          <input required value={form.phone} onChange={set('phone')}
                 className="rounded-lg border border-gray-300 p-2 font-normal" />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          City <span className="font-normal text-gray-500">(optional)</span>
          <input value={form.city} onChange={set('city')}
                 className="rounded-lg border border-gray-300 p-2 font-normal" />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          First language <span className="font-normal text-gray-500">(optional)</span>
          <input value={form.first_language} onChange={set('first_language')}
                 className="rounded-lg border border-gray-300 p-2 font-normal" />
        </label>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button type="submit" disabled={busy}
                className="rounded-lg bg-purple-600 text-white py-2 font-medium disabled:opacity-50">
          {busy ? 'Saving…' : 'Save and continue'}
        </button>
      </form>
    </div>
  )
}
