import { useState } from 'react'
import { createAttempt, getItems, getReport, pollReport, submitAttempt } from './api'
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
  const [error, setError] = useState(null)

  const handleBegin = async (name) => {
    const { items: fetchedItems } = await getItems()
    const { attempt_id } = await createAttempt(name)
    setItems(fetchedItems)
    setAttemptId(attempt_id)
    setScreen('check')
  }

  const handleTestComplete = async () => {
    setScreen('submitting')
    try {
      await submitAttempt(attemptId)
      const fetchedReport = await pollReport(attemptId)
      setReport(fetchedReport)
      setScreen('report')
    } catch {
      setError('Could not score your attempt. Please try again.')
      setScreen('test')
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 py-10">
      {error && <p className="text-center text-sm text-red-600 mb-4">{error}</p>}
      {screen === 'start' && <Start onBegin={handleBegin} />}
      {screen === 'check' && <DeviceCheck onConfirmed={() => setScreen('test')} />}
      {screen === 'test' && (
        <Test attemptId={attemptId} items={items} onComplete={handleTestComplete} />
      )}
      {screen === 'submitting' && <Submitting />}
      {screen === 'report' && report && <Report report={report} />}
    </main>
  )
}

function App() {
  return window.location.pathname === '/recruiter' ? <RecruiterApp /> : <CandidateApp />
}

export default App
