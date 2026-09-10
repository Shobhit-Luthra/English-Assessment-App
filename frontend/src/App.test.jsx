import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('./api', () => ({
  createAttempt: vi.fn(),
  getAttemptItems: vi.fn(),
  getReport: vi.fn(),
  pollReport: vi.fn(),
  submitAttempt: vi.fn(),
  submitResponse: vi.fn(),
  uploadAudio: vi.fn(),
  listAttempts: vi.fn(),
}))
import { getAttemptItems } from './api'
import App from './App'

afterEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
})

test('resumes an in-progress attempt from localStorage', async () => {
  localStorage.setItem('assessment.session', JSON.stringify({ attemptId: 'a1', index: 1 }))
  getAttemptItems.mockResolvedValue({
    items: [
      { id: 'g1', type: 'mcq', prompt: 'Q1', options: ['a', 'b'], time_limit_s: 40 },
      { id: 'g2', type: 'mcq', prompt: 'Q2', options: ['a', 'b'], time_limit_s: 40 },
    ],
  })
  render(<App />)
  await waitFor(() => expect(screen.getByText('Q2')).toBeInTheDocument())
})

test('clamps an out-of-range saved index', async () => {
  localStorage.setItem('assessment.session', JSON.stringify({ attemptId: 'a1', index: 99 }))
  getAttemptItems.mockResolvedValue({
    items: [
      { id: 'g1', type: 'mcq', prompt: 'Q1', options: ['a', 'b'], time_limit_s: 40 },
      { id: 'g2', type: 'mcq', prompt: 'Q2', options: ['a', 'b'], time_limit_s: 40 },
    ],
  })
  render(<App />)
  await waitFor(() => expect(screen.getByText('Q2')).toBeInTheDocument())
})

test('clears the session and stays on start when the attempt is gone', async () => {
  localStorage.setItem('assessment.session', JSON.stringify({ attemptId: 'dead', index: 0 }))
  getAttemptItems.mockRejectedValue(new Error('404'))
  render(<App />)
  await waitFor(() => expect(localStorage.getItem('assessment.session')).toBeNull())
})
