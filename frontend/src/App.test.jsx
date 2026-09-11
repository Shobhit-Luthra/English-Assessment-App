import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App'

vi.mock('./api', () => ({
  getMe: vi.fn(),
  logout: vi.fn(),
  getMyProfile: vi.fn(),
  getMyAttempts: vi.fn().mockResolvedValue([]),
  listCandidates: vi.fn().mockResolvedValue([]),
  getReport: vi.fn(),
  rescoreAttempt: vi.fn(),
  pollReport: vi.fn(),
  fetchAnalytics: vi.fn().mockResolvedValue({
    total_candidates_tested: 0, total_attempts: 0, completed_attempts: 0,
    in_progress_attempts: 0,
    cir: { average: null, recommended: 0, borderline: 0, not_recommended: 0, pass_rate: null },
    sections: {},
    decisions: { hired: 0, rejected: 0, pending: 0, total: 0 },
  }),
}))
import { getMe, getMyProfile, getReport, pollReport, rescoreAttempt } from './api'

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

test('an admin can preview recruiter navigation without admin controls', async () => {
  getMe.mockResolvedValue({
    email: 'a@x.com', permissions: ['roles.manage', 'candidates.view', 'analytics.view'],
    role: { name: 'admin' }, profile: null,
  })
  renderAt('/recruiter-preview')
  await waitFor(() => expect(screen.getByText(/previewing recruiter workspace/i)).toBeInTheDocument())
  expect(screen.getByRole('link', { name: /return to admin/i })).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument()
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

const failedReport = {
  attempt_id: 'a1', name: 'Alice', status: 'error', error: 'judge_unavailable',
  error_message: 'The scoring engine was unavailable.', scores: [],
}

test('a recruiter can re-score a failed attempt from the report page', async () => {
  getMe.mockResolvedValue({
    email: 'r@x.com', permissions: ['candidates.view'], role: { name: 'recruiter' },
  })
  getReport.mockResolvedValue(failedReport)
  renderAt('/report/a1')
  await waitFor(() => expect(screen.getByRole('button', { name: /re-score/i })).toBeInTheDocument())
})

test('a candidate sees the failure message but no re-score control', async () => {
  getMe.mockResolvedValue({
    email: 'c@x.com', permissions: ['test.take', 'report.view_own'], role: { name: 'candidate' },
    profile: { full_name: 'C' },
  })
  getReport.mockResolvedValue(failedReport)
  renderAt('/report/a1')
  await waitFor(() => expect(screen.getByText(/scoring engine was unavailable/i)).toBeInTheDocument())
  expect(screen.queryByRole('button', { name: /re-score/i })).not.toBeInTheDocument()
})

test('re-score runs the pipeline and shows the finished report', async () => {
  getMe.mockResolvedValue({
    email: 'r@x.com', permissions: ['candidates.view'], role: { name: 'recruiter' },
  })
  getReport.mockResolvedValue(failedReport)
  rescoreAttempt.mockResolvedValue({ ok: true })
  pollReport.mockResolvedValue({ ...failedReport, status: 'done', error: null, error_message: null,
    scores: [{ dimension: 'cir', band: 5, evidence: {} }] })
  renderAt('/report/a1')
  await userEvent.click(await screen.findByRole('button', { name: /re-score/i }))
  await waitFor(() => expect(screen.getByText("5 / 6")).toBeInTheDocument())
  expect(rescoreAttempt).toHaveBeenCalledWith('a1')
  expect(pollReport).toHaveBeenCalledWith('a1')
})

test('a failed re-score keeps the report and shows an inline error', async () => {
  getMe.mockResolvedValue({
    email: 'r@x.com', permissions: ['candidates.view'], role: { name: 'recruiter' },
  })
  getReport.mockResolvedValue(failedReport)
  rescoreAttempt.mockRejectedValue(new Error('409'))
  renderAt('/report/a1')
  await userEvent.click(await screen.findByRole('button', { name: /re-score/i }))
  await waitFor(() => expect(screen.getByText(/could not start re-scoring/i)).toBeInTheDocument())
  expect(screen.queryByText(/report not available/i)).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: /re-score/i })).toBeEnabled()
})
