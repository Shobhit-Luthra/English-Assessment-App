import { useEffect, useState } from 'react'
import { fetchAnalytics } from '../api'

const SECTIONS = [
  ['understanding', 'Understanding'],
  ['speaking', 'Speaking'],
  ['writing', 'Writing'],
]

function Stat({ label, value, sub }) {
  return (
    <div className="py-1">
      <div className="text-3xl font-semibold tabular-nums">{value}</div>
      <div className="mt-1 text-sm text-gray-500">{label}</div>
      {sub && <div className="text-xs text-gray-400">{sub}</div>}
    </div>
  )
}

function SectionBar({ label, value }) {
  const pct = value == null ? 0 : Math.round((value / 6) * 100)
  return (
    <div className="flex items-center gap-4 border-b py-2">
      <span className="w-32 text-sm text-gray-600">{label}</span>
      <div className="flex-1 h-2 rounded-full bg-gray-100 overflow-hidden">
        <div className="h-full rounded-full bg-blue-700" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-16 text-right font-mono text-sm tabular-nums">{value ?? '-'} / 6</span>
    </div>
  )
}

function Distribution({ title, buckets, total }) {
  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-sm font-medium">{title}</h3>
      <div className="flex h-3 rounded-full bg-gray-100 overflow-hidden">
        {buckets.map(([label, count, color]) => (
          <div
            key={label}
            className={color}
            style={{ width: total ? `${(count / total) * 100}%` : '0%' }}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-gray-600">
        {buckets.map(([label, count, color]) => (
          <span key={label} className="flex items-center gap-1.5">
            <span className={`inline-block h-2.5 w-2.5 rounded-full ${color}`} />
            {label}: <span className="font-semibold tabular-nums">{count}</span>
          </span>
        ))}
      </div>
    </div>
  )
}

export default function Analytics() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchAnalytics()
      .then(setData)
      .catch(() => setError('Could not load analytics.'))
  }, [])

  if (error) return <p className="p-6 text-center text-red-600">{error}</p>
  if (!data) return <p className="p-6 text-center text-gray-500">Loading...</p>

  const { cir, sections, decisions, benchmarks } = data
  const passRate = cir.pass_rate == null ? '-' : `${Math.round(cir.pass_rate * 100)}%`

  return (
    <div className="max-w-4xl mx-auto p-6 flex flex-col gap-8">
      <h1 className="text-2xl font-semibold">Analytics</h1>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
        <Stat label="Candidates tested" value={data.total_candidates_tested} />
        <Stat label="Completed tests" value={data.completed_attempts} />
        <Stat label="In progress" value={data.in_progress_attempts} />
        <Stat label="Average overall" value={cir.average ?? '-'} sub="out of 6" />
        <Stat label="Recommended rate" value={passRate} sub="level 5 or above" />
      </div>

      {data.completed_attempts > 0 ? (
        <>
          <section className="flex flex-col gap-1">
            <h2 className="text-lg font-semibold mb-1">Average score by section</h2>
            {SECTIONS.map(([key, label]) => (
              <SectionBar key={key} label={label} value={sections[key]} />
            ))}
          </section>

          <div className="grid gap-6 sm:grid-cols-3">
            <div className="flex flex-col gap-3">
              <h3 className="text-sm font-medium">Candidate benchmarks</h3>
              <div className="flex flex-col gap-1.5 text-sm text-gray-600">
                <div>
                  <span className="text-gray-400">Typical score:</span>{' '}
                  <span className="font-semibold tabular-nums">{benchmarks.median ?? '-'}</span>
                  <span className="text-gray-400"> / 6</span>
                </div>
                <div>
                  <span className="text-gray-400">Top 25% score at least:</span>{' '}
                  <span className="font-semibold tabular-nums">{benchmarks.top_25 ?? '-'}</span>
                  <span className="text-gray-400"> / 6</span>
                </div>
              </div>
            </div>

            <Distribution
              title="Recommendation spread"
              total={cir.recommended + cir.borderline + cir.not_recommended}
              buckets={[
                ['Recommended', cir.recommended, 'bg-green-500'],
                ['Borderline', cir.borderline, 'bg-yellow-400'],
                ['Not recommended', cir.not_recommended, 'bg-red-500'],
              ]}
            />
            <Distribution
              title="Hire / Reject decisions"
              total={decisions.total}
              buckets={[
                ['Hired', decisions.hired, 'bg-green-500'],
                ['Rejected', decisions.rejected, 'bg-red-500'],
                ['Pending', decisions.pending, 'bg-gray-300'],
              ]}
            />
          </div>
        </>
      ) : (
        <p className="text-gray-500">No completed attempts yet - analytics appear once candidates finish.</p>
      )}
    </div>
  )
}
