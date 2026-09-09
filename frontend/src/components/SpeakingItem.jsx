import { useEffect, useState } from 'react'
import { useRecorder } from '../hooks/useRecorder'
import Timer from './Timer'

// Parent renders this with key={item.id}, so a new item remounts the
// component and resets all state below for free - no reset effect needed.
export default function SpeakingItem({ item, onSubmitted }) {
  const [started, setStarted] = useState(false)
  const [error, setError] = useState(null)
  const { isRecording, blob, start, stop } = useRecorder()

  const phase = !started ? 'prep' : isRecording || !blob ? 'recording' : 'review'

  const beginRecording = async () => {
    setStarted(true)
    try {
      await start(item.time_limit_s)
    } catch {
      setError('Microphone access was denied.')
      setStarted(false)
    }
  }

  const audioUrl = blob ? URL.createObjectURL(blob) : null
  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl)
    }
  }, [audioUrl])

  return (
    <div className="flex flex-col gap-4 text-left">
      {item.type === 'read_aloud' && (
        <p className="text-lg font-medium bg-gray-50 rounded-lg p-4">{item.reference_text}</p>
      )}
      {item.type === 'situational' && <p className="text-lg font-medium">{item.prompt}</p>}

      {phase === 'prep' && (
        <div className="flex flex-col items-center gap-3">
          <p className="text-sm text-gray-500">Prepare your answer. Recording starts when the timer ends.</p>
          <Timer seconds={item.prep_s} itemKey={item.id} onExpire={beginRecording} />
        </div>
      )}

      {phase === 'recording' && (
        <div className="flex flex-col items-center gap-3">
          <p className="text-sm font-medium text-red-600">Recording...</p>
          <Timer seconds={item.time_limit_s} itemKey={`${item.id}-rec`} onExpire={stop} />
          <button
            type="button"
            onClick={stop}
            disabled={!isRecording}
            className="rounded-lg border border-gray-300 px-5 py-2 text-sm font-medium text-gray-700 disabled:opacity-50"
          >
            Stop &amp; review
          </button>
        </div>
      )}

      {phase === 'review' && audioUrl && (
        <div className="flex flex-col gap-3">
          {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
          <audio controls src={audioUrl} className="w-full" />
          <button
            type="button"
            onClick={() => onSubmitted(blob)}
            className="rounded-lg bg-purple-600 text-white px-6 py-2 font-medium self-end"
          >
            Submit
          </button>
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  )
}
