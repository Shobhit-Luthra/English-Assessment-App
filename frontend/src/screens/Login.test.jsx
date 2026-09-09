import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('../api', () => ({ login: vi.fn(), getMe: vi.fn(), logout: vi.fn() }))
import { login, getMe } from '../api'
import { AuthProvider } from '../auth/AuthContext'
import Login from './Login'

afterEach(() => vi.clearAllMocks())

function tree() {
  getMe.mockRejectedValue(Object.assign(new Error('401'), { status: 401 }))
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<p>home</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

test('successful login navigates home', async () => {
  const user = userEvent.setup()
  login.mockResolvedValue({ email: 'a@b.com' })
  getMe.mockResolvedValue({ email: 'a@b.com', permissions: [], role: { name: 'candidate' }, profile: {} })
  tree()
  await user.type(screen.getByLabelText(/email/i), 'a@b.com')
  await user.type(screen.getByLabelText(/password/i), 'longenough12')
  await user.click(screen.getByRole('button', { name: /sign in/i }))
  await waitFor(() => expect(screen.getByText('home')).toBeInTheDocument())
})

test('a failed login shows the error', async () => {
  const user = userEvent.setup()
  login.mockRejectedValue(Object.assign(new Error('401'), { status: 401 }))
  tree()
  await user.type(screen.getByLabelText(/email/i), 'a@b.com')
  await user.type(screen.getByLabelText(/password/i), 'wrong')
  await user.click(screen.getByRole('button', { name: /sign in/i }))
  await waitFor(() => expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument())
})
