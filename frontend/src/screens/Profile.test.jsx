import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('../api', () => ({ putProfile: vi.fn(), getMe: vi.fn(), logout: vi.fn() }))
import { putProfile, getMe } from '../api'
import { AuthProvider } from '../auth/AuthContext'
import Profile from './Profile'

afterEach(() => vi.clearAllMocks())

test('saving the profile navigates to the test', async () => {
  const user = userEvent.setup()
  getMe.mockResolvedValue({
    email: 'c@x.com', permissions: ['test.take'], role: { name: 'candidate' }, profile: null,
  })
  putProfile.mockResolvedValue({ full_name: 'Cee Andidate', phone: '123' })
  render(
    <MemoryRouter initialEntries={['/profile']}>
      <AuthProvider>
        <Routes>
          <Route path="/profile" element={<Profile />} />
          <Route path="/test" element={<p>test screen</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
  await waitFor(() => screen.getByText(/your details/i))
  await user.type(screen.getByLabelText(/full name/i), 'Cee Andidate')
  await user.type(screen.getByLabelText(/phone/i), '9990001111')
  await user.click(screen.getByRole('button', { name: /save|continue/i }))
  await waitFor(() => expect(screen.getByText('test screen')).toBeInTheDocument())
})
