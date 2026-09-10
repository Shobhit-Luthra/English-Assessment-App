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
  getMe: vi.fn(),
  logout: vi.fn(),
}))
import { createAttempt, getMe } from '../api'
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
