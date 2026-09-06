import { useState } from 'react'
import McqItem from '../components/McqItem'
import SpeakingItem from '../components/SpeakingItem'
import Timer from '../components/Timer'
import WritingItem from '../components/WritingItem'
import { submitResponse, uploadAudio } from '../api'

const SPEAKING_TYPES = new Set(['read_aloud', 'situational'])

export default function Test({ attemptId, items, onComplete }) {
  const [index, setIndex] = useState(0)
  const [answers, setAnswers] = useState({})
  const [error, setError] = useState(null)

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
      <div className="flex items-center justify-between text-sm text-gray-500">
        <span>
          Item {index + 1} of {items.length}
        </span>
        {!isSpeaking && item.time_limit_s && (
          <Timer seconds={item.time_limit_s} itemKey={item.id} onExpire={goNext} />
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
