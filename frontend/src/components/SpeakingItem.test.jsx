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

const stream = () => ({ getTracks: () => [{ stop: vi.fn() }] })

beforeEach(() => {
  lastRecorder = undefined
  globalThis.MediaRecorder = FakeMediaRecorder
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:fake')
  globalThis.URL.revokeObjectURL = vi.fn()
  Object.defineProperty(globalThis.navigator, 'mediaDevices', {
    configurable: true,
    value: {},
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

const fastPrep = async () => {
  // prep timer (1s) auto-starts recording
  await act(() => new Promise((r) => setTimeout(r, 1100)))
}

test('the stop button ends recording and shows the review/submit step', async () => {
  navigator.mediaDevices.getUserMedia = vi.fn().mockResolvedValue(stream())
  const user = userEvent.setup()
  render(<SpeakingItem item={item} onSubmitted={vi.fn()} />)

  await fastPrep()
  await waitFor(() => expect(lastRecorder?.state).toBe('recording'))

  const stopButton = screen.getByRole('button', { name: /stop & review/i })
  await user.click(stopButton)

  expect(lastRecorder.state).toBe('inactive')
  const submit = await screen.findByRole('button', { name: /^submit$/i })
  await user.click(submit)
})

test('while the microphone prompt is pending the countdown does not start', async () => {
  // getUserMedia never resolves - the item must sit in "starting" without a
  // ticking timer or an active recorder.
  navigator.mediaDevices.getUserMedia = vi.fn().mockImplementation(() => new Promise(() => {}))
  render(<SpeakingItem item={item} onSubmitted={vi.fn()} />)

  await fastPrep()
  await waitFor(() => expect(screen.getByText(/accessing microphone/i)).toBeInTheDocument())
  expect(screen.queryByTestId('timer')).toBeNull()
  expect(lastRecorder).toBeUndefined()
})

test('cancelling a pending microphone prompt returns to the prep screen', async () => {
  let grantMic
  navigator.mediaDevices.getUserMedia = vi.fn().mockImplementation(
    () => new Promise((resolve) => { grantMic = resolve }),
  )
  const user = userEvent.setup()
  render(<SpeakingItem item={item} onSubmitted={vi.fn()} />)

  await fastPrep()
  await user.click(await screen.findByRole('button', { name: /^cancel$/i }))

  // Back to prep immediately; the stream that later resolves must be
  // discarded, never turned into a recording.
  expect(await screen.findByText(/prepare your answer/i)).toBeInTheDocument()
  expect(screen.getByTestId('timer')).toBeInTheDocument()

  grantMic?.(stream())
  await act(() => new Promise((r) => setTimeout(r, 0)))
  expect(lastRecorder).toBeUndefined()
})