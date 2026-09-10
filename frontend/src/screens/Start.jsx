import { useState } from 'react'
import { Link } from 'react-router-dom'

const ORIENTATION = [
  ['Grammar & Listening', 'Multiple-choice questions'],
  ['Writing', 'A short written response'],
  ['Speaking', 'Two recorded answers'],
]

export default function Start({ displayName, onBegin }) {
  const [consent, setConsent] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const canBegin = consent && !submitting

  const handleBegin = async () => {
    setSubmitting(true)
    setError(null)
    try {
      await onBegin()
    } catch {
      setError('Could not start the test. Please try again.')
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-md mx-auto flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Your English Assessment</h1>
      </div>
      <p className="text-sm text-gray-600">
        Signed in as <span className="font-medium">{displayName}</span>.{' '}
        <Link to="/profile" className="underline">Edit details</Link>
      </p>

      <div className="rounded-lg border border-gray-200 bg-white p-4 flex flex-col gap-2 text-sm">
        <span className="font-medium">Before you begin</span>
        <ul className="flex flex-col gap-1 text-gray-600">
          <li>Answers save automatically as you go.</li>
          <li>Speaking sections record your microphone, so pick a quiet spot.</li>
          <li>The whole test is timed and takes about 15 minutes.</li>
        </ul>
      </div>

      <div className="flex flex-col gap-2">
        <span className="text-sm font-medium">What's in the test</span>
        {ORIENTATION.map(([part, blurb]) => (
          <div key={part} className="flex items-baseline justify-between border-b pb-2 text-sm">
            <span className="font-medium">{part}</span>
            <span className="text-gray-500">{blurb}</span>
          </div>
        ))}
      </div>

      <label className="flex items-start gap-3 text-left text-sm text-gray-600">
        <input
          type="checkbox"
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
          className="mt-1 accent-blue-700"
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
        className="rounded-lg bg-blue-700 text-white py-3 font-medium disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {submitting ? 'Starting…' : 'Start Test'}
      </button>
    </div>
  )
}