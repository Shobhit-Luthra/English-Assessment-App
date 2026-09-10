import { useEffect, useRef, useState } from 'react'
import { createAttempt, getAttemptItems, getReport, pollReport, submitAttempt } from './api'
import { clearSession, loadSession } from './session'
import DeviceCheck from './screens/DeviceCheck'
import Recruiter from './screens/Recruiter'
import Report from './screens/Report'
import Start from './screens/Start'
import Submitting from './screens/Submitting'
import Test from './screens/Test'

// No router: the candidate flow is a useState state machine, and the
// recruiter view is reached at a separate path (there is nothing to link
// between them within a single candidate's session).
function RecruiterApp() {
  const [viewingReport, setViewingReport] = useState(null)

  if (viewingReport) {
    return (
      <main className="min-h-screen bg-gray-50 py-10">
        <div className="max-w-3xl mx-auto mb-4">
          <button
            type="button"
            onClick={() => setViewingReport(null)}
            className="text-sm text-purple-600 underline"
          >
            ← Back to candidates
          </button>
        </div>
        <Report report={viewingReport} />
      </main>
    )
  }

  return (
    <main className="min-h-screen bg-gray-50 py-10">
      <Recruiter
        onOpenReport={async (attemptId) => {
          const report = await getReport(attemptId)
          setViewingReport(report)
        }}
      />
    </main>
  )
}

function CandidateApp() {
  const [screen, setScreen] = useState('start')
  const [attemptId, setAttemptId] = useState(null)
  const [items, setItems] = useState([])
  const [report, setReport] = useState(null)
  const [initialIndex, setInitialIndex] = useState(0)
  const [submitError, setSubmitError] = useState(null)
  // Guards re-submission: once the attempt is submitted, retry only re-polls.
  const submittedRef = useRef(false)

  // Once we're past the last item the attempt can no longer take responses,
  // so there is nothing to go "back" to. A slow or flaky score must not drop
  // the candidate into a dead test screen - keep them on the submitting
  // screen with a retry that re-polls.
  const runScoring = async (id = attemptId) => {
    setSubmitError(null)
    setScreen('submitting')
    try {
      if (!submittedRef.current) {
        await submitAttempt(id)
        submittedRef.current = true
      }
      const fetchedReport = await pollReport(id)
      setReport(fetchedReport)
      setScreen('report')
      clearSession()
    } catch {
      setSubmitError(
        'Scoring is taking longer than expected. Your answers are saved - you can keep waiting.',
      )
    }
  }

  useEffect(() => {
    const saved = loadSession()
    if (!saved) return
    let cancelled = false
    getAttemptItems(saved.attemptId)
      .then(({ items: fetchedItems }) => {
        if (cancelled) return
        setItems(fetchedItems)
        setAttemptId(saved.attemptId)
        setInitialIndex(Math.min(Math.max(0, saved.index ?? 0), fetchedItems.length - 1))
        setScreen('test')
      })
      .catch(async () => {
        if (cancelled) return
        // Items fetch 409s once the attempt has been submitted. If the
        // candidate refreshed after finishing, recover the report/scoring
        // state instead of dumping them back to the start screen.
        try {
          const recovered = await getReport(saved.attemptId)
          if (cancelled) return
          setAttemptId(saved.attemptId)
          submittedRef.current = true
          if (recovered.status === 'scoring') {
            runScoring(saved.attemptId)
          } else {
            setReport(recovered)
            setScreen('report')
            clearSession()
          }
        } catch {
          if (!cancelled) clearSession()
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  const handleBegin = async (name) => {
    clearSession()
    submittedRef.current = false
    const { attempt_id } = await createAttempt(name)
    const { items: fetchedItems } = await getAttemptItems(attempt_id)
    setItems(fetchedItems)
    setAttemptId(attempt_id)
    setScreen('check')
  }

  const handleTestComplete = () => {
    runScoring()
  }

  return (
    <main className="min-h-screen bg-gray-50 py-10">
      {screen === 'start' && <Start onBegin={handleBegin} />}
      {screen === 'check' && <DeviceCheck onConfirmed={() => setScreen('test')} />}
      {screen === 'test' && (
        <Test
          attemptId={attemptId}
          items={items}
          onComplete={handleTestComplete}
          initialIndex={initialIndex}
        />
      )}
      {screen === 'submitting' && (
        <Submitting error={submitError} onRetry={runScoring} />
      )}
      {screen === 'report' && report && <Report report={report} />}
    </main>
  )
}

function App() {
  return window.location.pathname === '/recruiter' ? <RecruiterApp /> : <CandidateApp />
}

export default App
