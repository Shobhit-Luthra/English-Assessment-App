import { useEffect, useRef, useState } from 'react'

// Announce only at these thresholds - an aria-live region on the visible
// countdown would make a screen reader read every single second.
const THRESHOLD_MESSAGES = {
  60: '1 minute remaining',
  30: '30 seconds remaining',
  10: '10 seconds remaining',
  0: 'Time is up',
}

const SIZES = {
  sm: { box: 44, stroke: 4, font: 'text-xs' },
  md: { box: 72, stroke: 6, font: 'text-lg' },
}

// A circular countdown: an SVG ring that drains clockwise as time runs out,
// with the seconds remaining in the centre. `size` is "sm" (inline, on the
// question) or "md" (the standalone global timer, pinned top-right).
export default function Timer({ seconds, onExpire, itemKey, size = 'sm', label }) {
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
  const { box, stroke, font } = SIZES[size] || SIZES.sm
  const radius = (box - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const fraction = seconds > 0 ? Math.max(0, Math.min(1, remaining / seconds)) : 0

  return (
    <>
      <div
        className={`relative inline-flex items-center justify-center tabular-nums ${
          low ? 'text-amber-600' : 'text-gray-700'
        }`}
        style={{ width: box, height: box }}
        data-testid="timer"
        title={label}
      >
        <svg width={box} height={box} className="-rotate-90" aria-hidden="true">
          <circle
            cx={box / 2}
            cy={box / 2}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={stroke}
            className="text-gray-200"
          />
          <circle
            cx={box / 2}
            cy={box / 2}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={circumference * (1 - fraction)}
            className={low ? 'text-amber-500' : 'text-purple-600'}
            style={{ transition: 'stroke-dashoffset 0.2s linear' }}
          />
        </svg>
        <span className={`absolute font-mono font-semibold ${font}`}>{remaining}</span>
      </div>
      <span className="sr-only" aria-live="polite" data-testid="timer-announce">
        {THRESHOLD_MESSAGES[remaining] || ''}
      </span>
    </>
  )
}
