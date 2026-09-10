import { useEffect, useState } from 'react'
import { listCandidates, setCandidateDecision } from '../api'

const LEVEL = { 6: 'Outstanding', 5: 'Strong', 4: 'Capable', 3: 'Developing', 2: 'Basic', 1: 'Beginner' }

const REC = [
  { test: (b) => b >= 5, label: 'Recommended', className: 'bg-green-100 text-green-800' },
  { test: (b) => b === 4, label: 'Borderline', className: 'bg-yellow-100 text-yellow-800' },
  { test: () => true, label: 'Not recommended', className: 'bg-red-100 text-red-800' },
]

const DECISION_STYLES = {
  hired: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
  pending: 'bg-gray-100 text-gray-600',
}

const SKILLS = [
  ['understanding', 'Understanding'],
  ['speaking', 'Speaking'],
  ['writing', 'Writing'],
]

function initials(name) {
  return name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase()
}

function latestDone(row) {
  if (!row.attempts.length) return null
  return row.attempts.find((a) => a.status === 'done') ?? row.attempts[0]
}

function recommendation(band) {
  return REC.find((r) => r.test(band)) ?? REC[REC.length - 1]
}

function ScoreBar({ band }) {
  const pct = band != null ? Math.round((band / 6) * 100) : 0
  return (
    <div className="flex items-center gap-2 min-w-0">
      <div className="flex-1 h-1.5 rounded-full bg-gray-100 overflow-hidden">
        <div className="h-full rounded-full bg-blue-700 transition-all" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-right font-mono text-xs tabular-nums text-gray-600">
        {band != null ? band : '-'}
      </span>
    </div>
  )
}

export default function Recruiter({ onOpenReport }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(null)

  async function load() {
    try {
      setRows(await listCandidates())
    } catch {
      setError('Could not load candidates.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const decide = async (user_id, decision) => {
    setBusy(user_id)
    try {
      await setCandidateDecision(user_id, decision)
      await load()
    } catch {
      setError('Could not update the decision.')
    } finally {
      setBusy(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-20">
        <div className="h-8 w-8 rounded-full border-4 border-blue-200 border-t-blue-700 animate-spin" />
      </div>
    )
  }

  if (error) return <p className="p-6 text-center text-red-600">{error}</p>

  return (
    <div className="px-6 py-8 max-w-6xl mx-auto flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Candidates</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {rows.length === 0
              ? 'No one has taken the test yet.'
              : `${rows.length} ${rows.length === 1 ? 'candidate' : 'candidates'} total`}
          </p>
        </div>
      </div>

      {rows.length === 0 && (
        <div className="border border-dashed border-gray-300 rounded-xl py-16 text-center">
          <p className="text-gray-500">No candidates have taken the test yet.</p>
          <p className="text-sm text-gray-400 mt-1">Results appear here once someone completes an assessment.</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4">
        {rows.map((row) => {
          const latest = latestDone(row)
          const rec = latest?.cir != null ? recommendation(latest.cir) : null
          const date = latest?.created_at ? new Date(latest.created_at) : null
          return (
            <div key={row.user_id} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="p-5 flex flex-col gap-4">
                {/* Header row */}
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="h-10 w-10 rounded-full bg-blue-700 text-white flex items-center justify-center text-sm font-semibold shrink-0">
                      {initials(row.full_name || row.email)}
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium truncate">{row.full_name}</p>
                      <p className="text-sm text-gray-500 truncate">{row.email}</p>
                    </div>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${DECISION_STYLES[row.decision]}`}>
                      {row.decision}
                    </span>
                    {row.decided_by && (
                      <span className="text-xs text-gray-400 hidden sm:inline">
                        by {row.decided_by}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {latest?.status === 'done' && (
                      <button
                        type="button"
                        onClick={() => onOpenReport(latest.attempt_id)}
                        className="rounded-lg bg-blue-700 text-white text-sm font-medium px-4 py-2 hover:bg-blue-800"
                      >
                        View report
                      </button>
                    )}
                    <button
                      type="button"
                      disabled={busy === row.user_id || row.decision === 'hired'}
                      onClick={() => decide(row.user_id, 'hired')}
                      className="px-3 py-2 rounded-lg text-sm font-medium border border-green-300 text-green-700 hover:bg-green-50 disabled:opacity-40"
                    >
                      Hire
                    </button>
                    <button
                      type="button"
                      disabled={busy === row.user_id || row.decision === 'rejected'}
                      onClick={() => decide(row.user_id, 'rejected')}
                      className="px-3 py-2 rounded-lg text-sm font-medium border border-red-300 text-red-700 hover:bg-red-50 disabled:opacity-40"
                    >
                      Reject
                    </button>
                    {row.decision !== 'pending' && (
                      <button
                        type="button"
                        disabled={busy === row.user_id}
                        onClick={() => decide(row.user_id, 'pending')}
                        className="px-3 py-2 rounded-lg text-sm font-medium border border-gray-300 text-gray-600 hover:bg-gray-50 disabled:opacity-40"
                      >
                        Reset
                      </button>
                    )}
                  </div>
                </div>

                {/* Score metrics */}
                {latest?.cir != null && (
                  <div className="flex flex-col gap-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-baseline gap-2">
                        <span className="text-2xl font-semibold tabular-nums">{latest.cir}</span>
                        <span className="text-sm text-gray-500">of 6</span>
                        <span className="text-sm font-medium text-gray-600 ml-1">{LEVEL[latest.cir]}</span>
                      </div>
                      {rec && (
                        <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${rec.className}`}>
                          {rec.label}
                        </span>
                      )}
                    </div>
                    {row.pct_stronger != null && (
                      <p className="text-xs text-gray-500">
                        Stronger than {Math.round(row.pct_stronger)}% of candidates
                      </p>
                    )}
                    <div className="flex flex-col gap-2">
                      {SKILLS.map(([key, label]) => (
                        <div key={key} className="flex flex-col gap-0.5">
                          <span className="text-xs text-gray-500">{label}</span>
                          <ScoreBar band={latest.sections?.[key] ?? null} />
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Footer meta */}
                <div className="flex flex-wrap items-center gap-4 text-xs text-gray-400 border-t border-gray-100 pt-3">
                  <span>{row.attempts.length} {row.attempts.length === 1 ? 'attempt' : 'attempts'}</span>
                  {date && <span>Last: {date.toLocaleDateString()}</span>}
                </div>
              </div>

              {/* Attempt history */}
              {row.attempts.length > 1 && (
                <div className="border-t border-gray-100 bg-gray-50 px-5 py-3">
                  <p className="text-xs font-medium text-gray-500 mb-2">Attempt history</p>
                  <div className="flex flex-col gap-1.5">
                    {row.attempts.map((a) => (
                      <div key={a.attempt_id} className="flex items-center justify-between text-xs">
                        <span className="text-gray-500">
                          {new Date(a.created_at).toLocaleString()}
                          {a.cir != null ? ` - CIR ${a.cir}` : ''}
                        </span>
                        <span className="flex items-center gap-2">
                          <span className="capitalize text-gray-400">{a.status}</span>
                          {a.status === 'done' && (
                            <button
                              type="button"
                              onClick={() => onOpenReport(a.attempt_id)}
                              className="text-blue-700 font-medium hover:underline"
                            >
                              View
                            </button>
                          )}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
