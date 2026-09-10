import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import Results from './Results'

vi.mock('../api', () => ({
  getMyProfile: vi.fn(),
  getMyAttempts: vi.fn(),
}))

import { getMyAttempts, getMyProfile } from '../api'

afterEach(() => vi.clearAllMocks())

function mockData() {
  getMyProfile.mockResolvedValue({ full_name: 'Alice Chen', decision: 'hired' })
  getMyAttempts.mockResolvedValue([
    { attempt_id: 'a1', status: 'done', created_at: '2026-09-01T10:00:00Z', cir: 6 },
    { attempt_id: 'a2', status: 'in_progress', created_at: '2026-09-02T10:00:00Z', cir: null },
  ])
}

test('shows decision status, attempts and a resume link', async () => {
  mockData()
  render(
    <MemoryRouter>
      <Results />
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByText(/hired/i)).toBeInTheDocument())
  expect(screen.getByText(/Alice Chen/i)).toBeInTheDocument()
  expect(screen.getByText(/CIR 6/i)).toBeInTheDocument()
  expect(screen.getByText(/view report/i)).toBeInTheDocument()
  expect(screen.getByText(/resume test/i)).toBeInTheDocument()
})

test('asks candidates without a profile to set up details', async () => {
  getMyProfile.mockResolvedValue(null)
  getMyAttempts.mockResolvedValue([])
  render(
    <MemoryRouter>
      <Results />
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByText(/set up your details/i)).toBeInTheDocument())
})