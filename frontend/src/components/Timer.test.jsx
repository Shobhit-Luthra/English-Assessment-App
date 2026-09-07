import { render, screen, act } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import Timer from './Timer'

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

test('shows amber styling under 10 seconds remaining', async () => {
  render(<Timer seconds={12} itemKey="x" onExpire={vi.fn()} />)
  const el = screen.getByTestId('timer')
  expect(el.className).not.toContain('amber')
  await act(async () => { vi.advanceTimersByTime(3000) })
  expect(el.className).toContain('amber')
})

test('calls onExpire once when it reaches zero', async () => {
  const onExpire = vi.fn()
  render(<Timer seconds={2} itemKey="x" onExpire={onExpire} />)
  await act(async () => { vi.advanceTimersByTime(5000) })
  expect(onExpire).toHaveBeenCalledTimes(1)
})
