import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import { AuthProvider } from './AuthContext'
import RequireAuth from './RequireAuth'

vi.mock('../api', () => ({ getMe: vi.fn(), logout: vi.fn() }))
import { getMe } from '../api'

afterEach(() => vi.clearAllMocks())

function tree(initial = '/secret') {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<p>login page</p>} />
          <Route path="/secret" element={
            <RequireAuth permission="candidates.view"><p>secret</p></RequireAuth>
          } />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

test('unauthenticated user is redirected to /login', async () => {
  getMe.mockRejectedValue(Object.assign(new Error('401'), { status: 401 }))
  tree()
  await waitFor(() => expect(screen.getByText('login page')).toBeInTheDocument())
})

test('authenticated user lacking the permission sees Forbidden', async () => {
  getMe.mockResolvedValue({ email: 'a@b.com', permissions: ['test.take'], role: { name: 'candidate' } })
  tree()
  await waitFor(() => expect(screen.getByText(/don't have access/i)).toBeInTheDocument())
})

test('authenticated user with the permission sees the page', async () => {
  getMe.mockResolvedValue({ email: 'a@b.com', permissions: ['candidates.view'], role: { name: 'recruiter' } })
  tree()
  await waitFor(() => expect(screen.getByText('secret')).toBeInTheDocument())
})
