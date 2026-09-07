import { render, screen, act } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import Test from './Test'

vi.mock('../api', () => ({
  submitResponse: vi.fn().mockResolvedValue({ ok: true }),
  uploadAudio: vi.fn().mockResolvedValue({ ok: true }),
}))
import { submitResponse } from '../api'

const items = [
  { id: 'g1', type: 'mcq', prompt: 'Q1', options: ['a', 'b', 'c', 'd'], time_limit_s: 2 },
  { id: 'g2', type: 'mcq', prompt: 'Q2', options: ['a', 'b', 'c', 'd'], time_limit_s: 2 },
]

beforeEach(() => vi.useFakeTimers())
afterEach(() => { vi.useRealTimers(); vi.clearAllMocks() })

test('per-question timer expiry advances to the next item', async () => {
  render(<Test attemptId="a1" items={items} onComplete={vi.fn()} />)
  expect(screen.getByText('Q1')).toBeInTheDocument()
  await act(async () => { vi.advanceTimersByTime(2100) })
  expect(screen.getByText('Q2')).toBeInTheDocument()
})

test('timer expiry on the last item completes the test', async () => {
  const onComplete = vi.fn()
  render(<Test attemptId="a1" items={[items[0]]} onComplete={onComplete} />)
  await act(async () => { vi.advanceTimersByTime(2100) })
  expect(onComplete).toHaveBeenCalledTimes(1)
})

test('a saved answer is persisted when the question timer expires', async () => {
  render(<Test attemptId="a1" items={items} onComplete={vi.fn()} />)
  await act(async () => {
    screen.getAllByRole('radio')[1].click()
  })
  submitResponse.mockClear()
  await act(async () => { vi.advanceTimersByTime(2100) })
  expect(submitResponse).toHaveBeenCalledWith('a1', 'g1', 'b')
})
