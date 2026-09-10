import { useEffect, useState } from 'react'
import { getReport, listAttempts } from '../api'

const SUB_DIMENSIONS = ['grammar', 'listening', 'speaking_fluency', 'writing_tone', 'situational_task_fulfilment']
const LABELS = {
  grammar: 'Grammar',
  listening: 'Listening',
  speaking_fluency: 'Speaking',
  writing_tone: 'Writing',
  situational_task_fulfilment: 'Task Fulfilment',
}

export default function Recruiter({ onOpenReport }) {
  const [rows, setRows] = useState([])
  const [sortKey, setSortKey] = useState('overall')
  const [sortDir, setSortDir] = useState('desc')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const attempts = await listAttempts()
        const withScores = await Promise.all(
          attempts.map(async (a) => {
            if (a.status !== 'done') {
              return { ...a, overall: null, subBands: {} }
            }
            const report = await getReport(a.attempt_id)
            const byDim = Object.fromEntries(report.scores.map((s) => [s.dimension, s.band]))
            const speakingBands = report.scores
              .filter((s) => s.dimension.startsWith('speaking_fluency_'))
              .map((s) => s.band)
            const subBands = {
              grammar: byDim.grammar,
              listening: byDim.listening,
              speaking_fluency: speakingBands.length
                ? speakingBands.reduce((s, b) => s + b, 0) / speakingBands.length
                : undefined,
              writing_tone: byDim.writing_tone,
              situational_task_fulfilment: byDim.situational_task_fulfilment,
            }
            return { ...a, overall: byDim.cir, subBands }
          }),
        )
        if (!cancelled) setRows(withScores)
      } catch {
        if (!cancelled) setError('Could not load attempts.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  const toggleSort = (key) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const sorted = [...rows].sort((a, b) => {
    const va = sortKey === 'overall' ? a.overall : a.subBands[sortKey]
    const vb = sortKey === 'overall' ? b.overall : b.subBands[sortKey]
    if (va == null && vb == null) return 0
    if (va == null) return 1
    if (vb == null) return -1
    return sortDir === 'desc' ? vb - va : va - vb
  })

  if (loading) return <p className="text-center p-6 text-gray-500">Loading...</p>
  if (error) return <p className="text-center p-6 text-red-600">{error}</p>

  return (
    <div className="max-w-4xl mx-auto p-6 overflow-x-auto">
      <h1 className="text-2xl font-semibold mb-4">Candidates</h1>
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b text-left text-gray-500">
            <th className="py-2 pr-4">Name</th>
            <th className="py-2 pr-4 cursor-pointer" onClick={() => toggleSort('overall')}>
              Overall {sortKey === 'overall' && (sortDir === 'desc' ? '↓' : '↑')}
            </th>
            {SUB_DIMENSIONS.map((dim) => (
              <th key={dim} className="py-2 pr-4 cursor-pointer" onClick={() => toggleSort(dim)}>
                {LABELS[dim]} {sortKey === dim && (sortDir === 'desc' ? '↓' : '↑')}
              </th>
            ))}
            <th className="py-2 pr-4">Status</th>
            <th className="py-2 pr-4">Submitted</th>
            <th className="py-2 pr-4">Report</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={row.attempt_id} className="border-b">
              <td className="py-2 pr-4">{row.name}</td>
              <td className="py-2 pr-4 font-mono">{row.overall ?? '-'}</td>
              {SUB_DIMENSIONS.map((dim) => (
                <td key={dim} className="py-2 pr-4 font-mono">
                  {row.subBands[dim] != null ? row.subBands[dim].toFixed(1) : '-'}
                </td>
              ))}
              <td className="py-2 pr-4 capitalize">{row.status}</td>
              <td className="py-2 pr-4 text-gray-500">
                {new Date(row.created_at).toLocaleString()}
              </td>
              <td className="py-2 pr-4">
                {row.status === 'done' && (
                  <button
                    type="button"
                    onClick={() => onOpenReport(row.attempt_id)}
                    className="text-purple-600 underline"
                  >
                    View
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
