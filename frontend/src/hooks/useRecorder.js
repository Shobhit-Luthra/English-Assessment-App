import { useCallback, useRef, useState } from 'react'

const MIME_TYPE = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
  ? 'audio/webm;codecs=opus'
  : 'audio/mp4'

export function useRecorder() {
  const [isRecording, setIsRecording] = useState(false)
  const [starting, setStarting] = useState(false)
  const [blob, setBlob] = useState(null)
  const mediaRecorderRef = useRef(null)
  const streamRef = useRef(null)
  const chunksRef = useRef([])
  const stopTimerRef = useRef(null)
  // A Stop click while getUserMedia is still pending marks this; when the
  // stream finally arrives it is discarded immediately instead of starting
  // a recording the user already asked to cancel.
  const cancelStartRef = useRef(false)

  const stop = useCallback(() => {
    clearTimeout(stopTimerRef.current)
    stopTimerRef.current = null
    cancelStartRef.current = true
    const recorder = mediaRecorderRef.current
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop()
    }
    setStarting(false)
    setIsRecording(false)
  }, [])

  const start = useCallback(
    async (timeLimitSeconds) => {
      setBlob(null)
      chunksRef.current = []
      cancelStartRef.current = false
      setStarting(true)
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (cancelStartRef.current) {
        // Stop was pressed while waiting on the permission prompt.
        stream.getTracks().forEach((t) => t.stop())
        setStarting(false)
        return false
      }
      streamRef.current = stream
      const recorder = new MediaRecorder(stream, { mimeType: MIME_TYPE })
      mediaRecorderRef.current = recorder

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }
      recorder.onstop = () => {
        setBlob(new Blob(chunksRef.current, { type: MIME_TYPE }))
        streamRef.current?.getTracks().forEach((t) => t.stop())
        streamRef.current = null
      }

      recorder.start()
      setStarting(false)
      setIsRecording(true)

      if (timeLimitSeconds) {
        stopTimerRef.current = setTimeout(stop, timeLimitSeconds * 1000)
      }
      return true
    },
    [stop],
  )

  const reset = useCallback(() => {
    setBlob(null)
    chunksRef.current = []
  }, [])

  return { isRecording, starting, blob, start, stop, reset, mimeType: MIME_TYPE }
}