import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { createAttempt, getAttemptItems, getReport, pollReport, submitAttempt } from '../api'
import { useAuth } from '../auth/AuthContext'
import { clearSession, loadSession } from '../testProgress'
import DeviceCheck from '../screens/DeviceCheck'
import Report from '../screens/Report'
import Start from '../screens/Start'
import Submitting from '../screens/Submitting'
import Test from '../screens/Test'

export default function CandidateFlow() {
  const { user } = useAuth()
  const [screen, setScreen] = useState('start')
  const [attemptId, setAttemptId] = useState(null)
  const [items, setItems] = useState([])
  const [report, setReport] = useState(null)
  const [initialIndex, setInitialIndex] = useState(0)
  const [submitError, setSubmitError] = useState(null)
  const submittedRef = useRef(false)

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

  const handleBegin = async () => {
    clearSession()
    submittedRef.current = false
    const { attempt_id } = await createAttempt()
    const { items: fetchedItems } = await getAttemptItems(attempt_id)
    setItems(fetchedItems)
    setAttemptId(attempt_id)
    setScreen('check')
  }

  const handleTestComplete = () => {
    runScoring()
  }

  return (
    <main className="py-10">
      {screen === 'start' && (
        <Start
          onBegin={handleBegin}
          displayName={user?.profile?.full_name ?? user?.display_name}
        />
      )}
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
      {screen === 'report' && report && (
        <div className="flex flex-col gap-4">
          <Report report={report} />
          <div className="text-center">
            <Link to="/results" className="rounded-lg bg-blue-700 text-white font-medium px-6 py-2.5 hover:bg-blue-800">
              Back to my results
            </Link>
          </div>
        </div>
      )}
    </main>
  )
}
