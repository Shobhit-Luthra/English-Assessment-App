import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App'

vi.mock('./api', () => ({
  getMe: vi.fn(),
  logout: vi.fn(),
  getMyProfile: vi.fn(),
  getMyAttempts: vi.fn().mockResolvedValue([]),
  listAttempts: vi.fn().mockResolvedValue([]),
  listCandidates: vi.fn().mockResolvedValue([]),
  fetchAnalytics: vi.fn().mockResolvedValue({
    total_candidates_tested: 0, total_attempts: 0, completed_attempts: 0,
    in_progress_attempts: 0,
    cir: { average: null, recommended: 0, borderline: 0, not_recommended: 0, pass_rate: null },
    sections: {},
    decisions: { hired: 0, rejected: 0, pending: 0, total: 0 },
  }),
}))
import { getMe, getMyProfile } from './api'

afterEach(() => vi.clearAllMocks())

const renderAt = (path) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )

test('a candidate with no profile lands on the profile page', async () => {
  getMe.mockResolvedValue({
    email: 'c@x.com',
    permissions: ['test.take', 'report.view_own'],
    role: { name: 'candidate' },
    profile: null,
  })
  renderAt('/')
  await waitFor(() => expect(screen.getByText(/your details/i)).toBeInTheDocument())
})

test('a candidate with a profile lands on their results page', async () => {
  getMe.mockResolvedValue({
    email: 'c@x.com',
    permissions: ['test.take', 'report.view_own'],
    role: { name: 'candidate' },
    profile: { full_name: 'Cee A', decision: 'pending' },
  })
  getMyProfile.mockResolvedValue({ full_name: 'Cee A', decision: 'pending' })
  renderAt('/')
  await waitFor(() => expect(screen.getByRole('heading', { name: /my results/i })).toBeInTheDocument())
  await waitFor(() => expect(screen.getByText(/pending/i)).toBeInTheDocument())
})

test('a recruiter lands on the dashboard', async () => {
  getMe.mockResolvedValue({
    email: 'r@x.com',
    permissions: ['candidates.view'],
    role: { name: 'recruiter' },
    profile: null,
  })
  renderAt('/')
  await waitFor(() => expect(screen.getByText(/no candidates have taken the test yet/i)).toBeInTheDocument())
})

test('an unauthenticated visitor to /admin is redirected to login', async () => {
  getMe.mockRejectedValue(Object.assign(new Error('401'), { status: 401 }))
  renderAt('/admin')
  await waitFor(() => expect(screen.getByRole('heading', { name: /sign in/i })).toBeInTheDocument())
})

test('an unauthenticated visitor to the home page sees the landing page', async () => {
  getMe.mockRejectedValue(Object.assign(new Error('401'), { status: 401 }))
  renderAt('/')
  await waitFor(() => expect(screen.getByText(/a better way to evaluate/i)).toBeInTheDocument())
})
