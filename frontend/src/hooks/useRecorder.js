import { useCallback, useRef, useState } from 'react'

const MIME_TYPE = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
  ? 'audio/webm;codecs=opus'
  : 'audio/mp4'

export function useRecorder() {
  const [isRecording, setIsRecording] = useState(false)
  const [blob, setBlob] = useState(null)
  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])
  const stopTimerRef = useRef(null)

  const stop = useCallback(() => {
    clearTimeout(stopTimerRef.current)
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }
    setIsRecording(false)
  }, [])

  const start = useCallback(
    async (timeLimitSeconds) => {
      setBlob(null)
      chunksRef.current = []
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream, { mimeType: MIME_TYPE })
      mediaRecorderRef.current = recorder

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }
      recorder.onstop = () => {
        setBlob(new Blob(chunksRef.current, { type: MIME_TYPE }))
        stream.getTracks().forEach((t) => t.stop())
      }

      recorder.start()
      setIsRecording(true)

      if (timeLimitSeconds) {
        stopTimerRef.current = setTimeout(stop, timeLimitSeconds * 1000)
      }
    },
    [stop],
  )

  const reset = useCallback(() => {
    setBlob(null)
    chunksRef.current = []
  }, [])

  return { isRecording, blob, start, stop, reset, mimeType: MIME_TYPE }
}
