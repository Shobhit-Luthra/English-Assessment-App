import { useEffect, useState } from 'react'
import { useRecorder } from '../hooks/useRecorder'
import Timer from './Timer'

// Parent renders this with key={item.id}, so a new item remounts the
// component and resets all state below for free - no reset effect needed.
export default function SpeakingItem({ item, onSubmitted }) {
  const [started, setStarted] = useState(false)
  const [error, setError] = useState(null)
  const { isRecording, starting, blob, start, stop } = useRecorder()

  // Explicit phases instead of deriving "recording" from "no blob yet":
  // a Stopped-but-not-yet-finalised clip must not look like it is still
  // recording.
  const phase = !started
    ? 'prep'
    : starting
      ? 'starting'
      : isRecording
        ? 'recording'
        : blob
          ? 'review'
          : 'finalizing'

  const beginRecording = async () => {
    setError(null)
    setStarted(true)
    try {
      const didStart = await start(item.time_limit_s)
      if (!didStart) setStarted(false) // Stop was pressed during mic permission
    } catch {
      setError('Microphone access was denied.')
      setStarted(false)
    }
  }

  const cancelStart = () => {
    stop()
    setStarted(false) // back to prep; useRecorder discards the pending stream
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

      {(phase === 'starting' || phase === 'recording') && (
        <div className="flex flex-col items-center gap-3">
          <p className="text-sm font-medium text-red-600">
            {phase === 'starting' ? 'Accessing microphone...' : 'Recording...'}
          </p>
          {phase === 'recording' && (
            <Timer seconds={item.time_limit_s} itemKey={`${item.id}-rec`} onExpire={stop} />
          )}
          {phase === 'starting' && <p className="text-xs text-gray-500">Please allow microphone access.</p>}
          <button
            type="button"
            onClick={phase === 'starting' ? cancelStart : stop}
            className="rounded-lg border border-gray-300 px-5 py-2 text-sm font-medium text-gray-700"
          >
            {phase === 'starting' ? 'Cancel' : 'Stop & review'}
          </button>
        </div>
      )}

      {phase === 'finalizing' && (
        <p className="text-center text-sm font-medium text-gray-600">
          Finalizing your recording...
        </p>
      )}

      {phase === 'review' && audioUrl && (
        <div className="flex flex-col gap-3">
          {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
          <audio controls src={audioUrl} className="w-full" />
          <button
            type="button"
            onClick={() => onSubmitted(blob)}
            className="rounded-lg bg-blue-700 text-white px-6 py-2 font-medium self-end"
          >
            Submit
          </button>
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  )
}