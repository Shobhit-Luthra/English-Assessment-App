import { render, screen, act, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import SpeakingItem from './SpeakingItem'

// A controllable MediaRecorder stand-in: start() flips state to 'recording',
// stop() flips it back and fires ondataavailable + onstop so useRecorder
// produces a blob.
let lastRecorder
class FakeMediaRecorder {
  static isTypeSupported() {
    return true
  }
  constructor() {
    this.state = 'inactive'
    this.ondataavailable = null
    this.onstop = null
    lastRecorder = this
  }
  start() {
    this.state = 'recording'
  }
  stop() {
    this.state = 'inactive'
    this.ondataavailable?.({ data: new Blob(['x'], { type: 'audio/webm' }) })
    this.onstop?.()
  }
}

beforeEach(() => {
  lastRecorder = undefined
  globalThis.MediaRecorder = FakeMediaRecorder
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:fake')
  globalThis.URL.revokeObjectURL = vi.fn()
  Object.defineProperty(globalThis.navigator, 'mediaDevices', {
    configurable: true,
    value: {
      getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] }),
    },
  })
})

afterEach(() => vi.clearAllMocks())

const item = {
  id: 's1',
  type: 'situational',
  prompt: 'Respond to the customer.',
  prep_s: 1,
  time_limit_s: 60,
}

test('the stop button ends recording and shows the review/submit step', async () => {
  const user = userEvent.setup()
  render(<SpeakingItem item={item} onSubmitted={vi.fn()} />)

  // prep timer (1s) auto-starts recording
  await act(() => new Promise((r) => setTimeout(r, 1100)))
  await waitFor(() => expect(lastRecorder?.state).toBe('recording'))

  const stopButton = screen.getByRole('button', { name: /stop & review/i })
  await user.click(stopButton)

  expect(lastRecorder.state).toBe('inactive')
  const submit = await screen.findByRole('button', { name: /^submit$/i })
  await user.click(submit)
})
