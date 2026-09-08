import { useEffect, useRef, useState } from 'react'
import McqItem from '../components/McqItem'
import Progress from '../components/Progress'
import SpeakingItem from '../components/SpeakingItem'
import Timer from '../components/Timer'
import WritingItem from '../components/WritingItem'
import { submitResponse, uploadAudio } from '../api'
import { saveSession } from '../session'

const SPEAKING_TYPES = new Set(['read_aloud', 'situational'])
const GLOBAL_LIMIT_S = 840

export default function Test({ attemptId, items, onComplete, initialIndex = 0 }) {
  const [index, setIndex] = useState(initialIndex)
  // Seed from the candidate's own saved answers so a resume-after-refresh
  // restores the writing textarea. MCQ is excluded: the stored value is the
  // canonical letter, which would highlight the wrong shuffled option (spec
  // Section 9).
  const [answers, setAnswers] = useState(() =>
    Object.fromEntries(
      items
        .filter((i) => i.type !== 'mcq' && i.response_text != null)
        .map((i) => [i.id, i.response_text]),
    ),
  )
  const [error, setError] = useState(null)
  const globalFiredRef = useRef(false)

  useEffect(() => {
    saveSession({ attemptId, index })
  }, [attemptId, index])

  const handleGlobalExpire = () => {
    if (globalFiredRef.current) return
    globalFiredRef.current = true
    onComplete()
  }

  const item = items[index]
  const isLast = index === items.length - 1
  const isSpeaking = item && SPEAKING_TYPES.has(item.type)

  const goNext = () => {
    setError(null)
    if (isLast) {
      onComplete()
    } else {
      setIndex((i) => i + 1)
    }
  }

  const handleTimerExpire = () => {
    const pending = answers[item.id]
    if (pending !== undefined && !isSpeaking) {
      // fire-and-forget: never block the advance on a slow save
      submitResponse(attemptId, item.id, pending).catch(() => {})
    }
    goNext()
  }

  const handleAnswer = async (value) => {
    setAnswers((prev) => ({ ...prev, [item.id]: value }))
    try {
      await submitResponse(attemptId, item.id, value)
    } catch {
      setError('Could not save your answer. Check your connection and try again.')
    }
  }

  const handleAudioSubmitted = async (blob) => {
    try {
      await uploadAudio(attemptId, item.id, blob, blob.type)
      goNext()
    } catch {
      setError('Could not upload your recording. Check your connection and try again.')
    }
  }

  if (!item) {
    return <p>No items to display.</p>
  }

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-6 p-6">
      {/* Global test timer: a standalone circle pinned to the top-right. */}
      <div className="fixed top-4 right-4 z-10 flex flex-col items-center gap-1 rounded-xl bg-white/90 p-2 shadow-sm backdrop-blur">
        <Timer
          seconds={GLOBAL_LIMIT_S}
          itemKey="global"
          onExpire={handleGlobalExpire}
          size="md"
          label="Time left in the whole test"
        />
        <span className="text-[10px] uppercase tracking-wide text-gray-400">Test</span>
      </div>

      <Progress items={items} index={index} />
      <div className="flex items-center justify-between text-sm text-gray-500">
        <span>
          Item {index + 1} of {items.length}
        </span>
        {!isSpeaking && item.time_limit_s && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">This question</span>
            <Timer
              seconds={item.time_limit_s}
              itemKey={item.id}
              onExpire={handleTimerExpire}
              size="sm"
              label="Time left on this question"
            />
          </div>
        )}
      </div>

      {item.type === 'mcq' && (
        <McqItem item={item} value={answers[item.id]} onAnswer={handleAnswer} />
      )}
      {item.type === 'text' && (
        <WritingItem item={item} value={answers[item.id]} onAnswer={handleAnswer} />
      )}
      {isSpeaking && (
        <SpeakingItem key={item.id} item={item} onSubmitted={handleAudioSubmitted} />
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      {!isSpeaking && (
        <button
          type="button"
          onClick={goNext}
          className="self-end rounded-lg bg-purple-600 text-white px-6 py-2 font-medium"
        >
          {isLast ? 'Finish' : 'Next'}
        </button>
      )}
    </div>
  )
}
