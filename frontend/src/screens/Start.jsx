import { useState } from 'react'

export default function Start({ onBegin }) {
  const [name, setName] = useState('')
  const [consent, setConsent] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const canBegin = name.trim().length > 0 && consent && !submitting

  const handleBegin = async () => {
    setSubmitting(true)
    setError(null)
    try {
      await onBegin(name.trim())
    } catch {
      setError('Could not start the test. Please try again.')
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-md mx-auto flex flex-col gap-6 p-6">
      <h1 className="text-2xl font-semibold">English Assessment</h1>
      <div className="flex flex-col gap-2 text-left">
        <label htmlFor="name" className="text-sm font-medium">
          Your name
        </label>
        <input
          id="name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="rounded-lg border border-gray-300 p-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
          placeholder="Full name"
        />
      </div>
      <label className="flex items-start gap-3 text-left text-sm text-gray-600">
        <input
          type="checkbox"
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
          className="mt-1 accent-purple-600"
        />
        <span>
          I consent to my microphone audio being recorded for the speaking sections of this
          assessment.
        </span>
      </label>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button
        type="button"
        disabled={!canBegin}
        onClick={handleBegin}
        className="rounded-lg bg-purple-600 text-white py-3 font-medium disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {submitting ? 'Starting...' : 'Begin'}
      </button>
    </div>
  )
}
