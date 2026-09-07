import { useEffect, useRef, useState } from 'react'

// Announce only at these thresholds - an aria-live region on the visible
// countdown would make a screen reader read every single second.
const THRESHOLD_MESSAGES = {
  60: '1 minute remaining',
  30: '30 seconds remaining',
  10: '10 seconds remaining',
  0: 'Time is up',
}

export default function Timer({ seconds, onExpire, itemKey }) {
  const [remaining, setRemaining] = useState(seconds)
  const onExpireRef = useRef(onExpire)
  onExpireRef.current = onExpire

  useEffect(() => {
    setRemaining(seconds)
    const start = Date.now()
    const interval = setInterval(() => {
      const left = seconds - Math.floor((Date.now() - start) / 1000)
      if (left <= 0) {
        setRemaining(0)
        clearInterval(interval)
        onExpireRef.current()
      } else {
        setRemaining(left)
      }
    }, 200)
    return () => clearInterval(interval)
    // itemKey forces the timer to restart when the current item changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seconds, itemKey])

  const low = remaining <= 10
  return (
    <>
      <div
        className={`text-sm font-mono tabular-nums ${low ? 'text-amber-600 font-semibold' : 'text-gray-600'}`}
        data-testid="timer"
      >
        {remaining}s
      </div>
      <span className="sr-only" aria-live="polite" data-testid="timer-announce">
        {THRESHOLD_MESSAGES[remaining] || ''}
      </span>
    </>
  )
}
