import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getMyAttempts, getMyProfile } from '../api'

const DECISION_STYLES = {
  hired: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
  pending: 'bg-gray-100 text-gray-600',
}

export default function Results() {
  const [profile, setProfile] = useState(null)
  const [attempts, setAttempts] = useState(null)
  const [refresh, setRefresh] = useState(0)

  useEffect(() => {
    let cancelled = false
    getMyProfile().then((me) => {
      if (!cancelled) setProfile(me)
    }).catch(() => {})
    getMyAttempts().then((rows) => {
      if (!cancelled) setAttempts(rows)
    }).catch(() => {})
    return () => {
      cancelled = true
    }
  }, [refresh])

  if (!profile) {
    return (
      <main className="py-10">
        <div className="max-w-2xl mx-auto px-6">
          <h1 className="text-2xl font-semibold mb-1">My results</h1>
          <p className="text-gray-500 mb-6">Complete your details to take the test.</p>
          <Link
            to="/profile"
            className="inline-block bg-blue-700 text-white rounded-lg px-4 py-2 font-medium"
          >
            Set up your details
          </Link>
        </div>
      </main>
    )
  }

  const decision = profile.decision ?? 'pending'
  const inProgress = attempts?.some((a) => a.status === 'in_progress' || a.status === 'scoring')

  return (
    <main className="py-10">
      <div className="max-w-2xl mx-auto px-6">
        <h1 className="text-2xl font-semibold mb-1">My results</h1>
        <p className="text-gray-500 mb-6">{profile.full_name}</p>

        <div className="flex items-center gap-3 pb-6 border-b">
          <span className="text-sm font-medium text-gray-500">Decision</span>
          <span
            className={`px-2.5 py-1 rounded text-sm font-medium capitalize ${
              DECISION_STYLES[decision]
            }`}
          >
            {decision}
          </span>
          {decision === 'pending' && (
            <span className="text-sm text-gray-500">
              A recruiter will review your results and update this.
            </span>
          )}
        </div>

        <div className="flex items-center justify-between mt-6 mb-2">
          <h2 className="text-sm font-medium text-gray-500">Attempts</h2>
          <button
            type="button"
            onClick={() => setRefresh((n) => n + 1)}
            className="text-sm text-blue-700 font-medium"
          >
            Refresh
          </button>
        </div>

        {attempts === null ? (
          <p className="text-gray-500">Loading…</p>
        ) : attempts.length === 0 ? (
          <p className="text-gray-500">
            You haven&apos;t taken the test yet. Start one below and your results will appear here.
          </p>
        ) : (
          <ul className="border divide-y divide-gray-200 rounded-lg">
            {attempts.map((a) => (
              <li key={a.attempt_id} className="flex items-center justify-between px-4 py-3">
                <div>
                  <p className="font-medium capitalize">{a.status}</p>
                  <p className="text-sm text-gray-500">
                    {new Date(a.created_at).toLocaleDateString()}
                    {a.status === 'done' && a.cir != null ? `  CIR ${a.cir}` : ''}
                  </p>
                </div>
                {a.status === 'done' && (
                  <Link
                    to={`/report/${a.attempt_id}`}
                    className="text-blue-700 font-medium text-sm"
                  >
                    View report
                  </Link>
                )}
                {a.status === 'scoring' && (
                  <span className="text-sm text-gray-400">Scoring…</span>
                )}
                {a.status === 'in_progress' && (
                  <Link to="/test" className="text-blue-700 font-medium text-sm">
                    Resume
                  </Link>
                )}
                {a.status === 'error' && (
                  <span className="text-sm text-red-600">
                    Scoring failed — a recruiter can re-run it
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}

        <div className="flex gap-3 mt-8">
          <Link
            to="/test"
            className="bg-blue-700 text-white rounded-lg px-4 py-2 font-medium"
          >
            {inProgress ? 'Resume test' : 'Start a new test'}
          </Link>
          <Link
            to="/profile"
            className="border border-gray-300 rounded-lg px-4 py-2 font-medium text-gray-700"
          >
            Edit details
          </Link>
        </div>
      </div>
    </main>
  )
}