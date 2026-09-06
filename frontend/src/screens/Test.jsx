import { useMemo, useState } from 'react'
import McqItem from '../components/McqItem'
import Timer from '../components/Timer'
import WritingItem from '../components/WritingItem'
import { submitResponse } from '../api'

// Day 1 supports text-only item types. Speaking items (read_aloud, situational)
// are added in Day 2 once the recorder exists.
const SUPPORTED_TYPES = new Set(['mcq', 'text'])

export default function Test({ attemptId, items, onComplete }) {
  const supportedItems = useMemo(() => items.filter((i) => SUPPORTED_TYPES.has(i.type)), [items])
  const [index, setIndex] = useState(0)
  const [answers, setAnswers] = useState({})
  const [error, setError] = useState(null)

  const item = supportedItems[index]
  const isLast = index === supportedItems.length - 1

  const persist = async (itemId, value) => {
    try {
      await submitResponse(attemptId, itemId, value)
    } catch {
      setError('Could not save your answer. Check your connection and try again.')
    }
  }

  const handleAnswer = (value) => {
    setAnswers((prev) => ({ ...prev, [item.id]: value }))
    persist(item.id, value)
  }

  const goNext = () => {
    setError(null)
    if (isLast) {
      onComplete()
    } else {
      setIndex((i) => i + 1)
    }
  }

  if (!item) {
    return <p>No items to display.</p>
  }

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between text-sm text-gray-500">
        <span>
          Item {index + 1} of {supportedItems.length}
        </span>
        {item.time_limit_s && (
          <Timer seconds={item.time_limit_s} itemKey={item.id} onExpire={goNext} />
        )}
      </div>

      {item.type === 'mcq' && (
        <McqItem item={item} value={answers[item.id]} onAnswer={handleAnswer} />
      )}
      {item.type === 'text' && (
        <WritingItem item={item} value={answers[item.id]} onAnswer={handleAnswer} />
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      <button
        type="button"
        onClick={goNext}
        className="self-end rounded-lg bg-purple-600 text-white px-6 py-2 font-medium"
      >
        {isLast ? 'Finish' : 'Next'}
      </button>
    </div>
  )
}
