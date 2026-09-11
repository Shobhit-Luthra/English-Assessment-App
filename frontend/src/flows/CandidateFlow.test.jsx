import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('../api', () => ({
  createAttempt: vi.fn().mockResolvedValue({ attempt_id: 'a1' }),
  getAttemptItems: vi.fn().mockResolvedValue({ items: [] }),
  submitAttempt: vi.fn(),
  pollReport: vi.fn(),
  getReport: vi.fn(),
  getHealth: vi.fn().mockResolvedValue({ ollama: true, whisper: true }),
  getMe: vi.fn(),
  logout: vi.fn(),
}))
import { createAttempt, getAttemptItems, getHealth, getMe, getReport, pollReport } from '../api'
import { AuthProvider } from '../auth/AuthContext'
import CandidateFlow from './CandidateFlow'

afterEach(() => vi.clearAllMocks())

test('Start Test creates an attempt with no name argument', async () => {
  const user = userEvent.setup()
  getMe.mockResolvedValue({
    email: 'c@x.com',
    display_name: 'Cee',
    permissions: ['test.take'],
    role: { name: 'candidate' },
    profile: { full_name: 'Cee Andidate' },
  })
  render(
    <MemoryRouter>
      <AuthProvider>
        <CandidateFlow />
      </AuthProvider>
    </MemoryRouter>,
  )
  await waitFor(() => screen.getByRole('button', { name: /start test/i }))
  await user.click(screen.getByRole('checkbox'))
  await user.click(screen.getByRole('button', { name: /start test/i }))
  await waitFor(() => expect(createAttempt).toHaveBeenCalledWith())
})

test('resuming a submitted attempt warns when the scoring engine is offline', async () => {
  localStorage.setItem('assessment.session', JSON.stringify({ attemptId: 'a9', index: 0 }))
  getMe.mockResolvedValue({ email: 'c@x.com', permissions: ['test.take'], role: { name: 'candidate' } })
  getAttemptItems.mockRejectedValueOnce(new Error('409'))
  getReport.mockResolvedValueOnce({ attempt_id: 'a9', status: 'scoring', scores: [] })
  getHealth.mockResolvedValueOnce({ ollama: false, whisper: true })
  pollReport.mockReturnValueOnce(new Promise(() => {}))
  render(
    <MemoryRouter>
      <AuthProvider>
        <CandidateFlow />
      </AuthProvider>
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByText(/scoring engine is offline/i)).toBeInTheDocument())
  localStorage.removeItem('assessment.session')
})
