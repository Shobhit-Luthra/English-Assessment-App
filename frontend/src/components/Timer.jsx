import { useEffect, useRef, useState } from 'react'

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

  return (
    <div className="text-sm font-mono tabular-nums text-gray-600" data-testid="timer">
      {remaining}s
    </div>
  )
}
