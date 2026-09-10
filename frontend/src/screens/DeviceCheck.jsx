import { useEffect, useRef, useState } from 'react'
import { useRecorder } from '../hooks/useRecorder'

const CHECK_DURATION_S = 5

export default function DeviceCheck({ onConfirmed }) {
  const { isRecording, blob, start, reset } = useRecorder()
  const [error, setError] = useState(null)
  const [confirmed, setConfirmed] = useState(false)
  const audioRef = useRef(null)

  const handleRecord = async () => {
    setError(null)
    reset()
    setConfirmed(false)
    try {
      await start(CHECK_DURATION_S)
    } catch {
      setError('Microphone access was denied. Please allow microphone access and try again.')
    }
  }

  const audioUrl = blob ? URL.createObjectURL(blob) : null

  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl)
    }
  }, [audioUrl])

  return (
    <div className="max-w-md mx-auto flex flex-col gap-6 p-6 text-center">
      <h1 className="text-xl font-semibold">Device Check</h1>
      <p className="text-sm text-gray-600">
        We need to check your microphone before you begin. Record a short clip, then play it back
        to confirm you can hear yourself.
      </p>

      <button
        type="button"
        onClick={handleRecord}
        disabled={isRecording}
        className="rounded-lg bg-purple-600 text-white py-3 font-medium disabled:opacity-40"
      >
        {isRecording ? `Recording... ${CHECK_DURATION_S}s` : 'Record 5 seconds'}
      </button>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {audioUrl && (
        <div className="flex flex-col gap-3">
          {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
          <audio ref={audioRef} controls src={audioUrl} className="w-full" />
          <label className="flex items-center gap-2 justify-center text-sm">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              className="accent-purple-600"
            />
            I could hear myself clearly
          </label>
        </div>
      )}

      <button
        type="button"
        onClick={onConfirmed}
        disabled={!confirmed}
        className="rounded-lg bg-green-600 text-white py-3 font-medium disabled:opacity-40 disabled:cursor-not-allowed"
      >
        Continue
      </button>
    </div>
  )
}
