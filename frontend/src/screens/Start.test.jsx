import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import Start from './Start'

afterEach(() => vi.clearAllMocks())

const renderGate = (props = {}) =>
  render(
    <MemoryRouter>
      <Start displayName="Cee Andidate" onBegin={props.onBegin ?? vi.fn().mockResolvedValue()} />
    </MemoryRouter>,
  )

test('lists the test sections and shows the signed-in name', () => {
  renderGate()
  expect(screen.getByText(/grammar & listening/i)).toBeInTheDocument()
  expect(screen.getByText(/a short written response/i)).toBeInTheDocument()
  expect(screen.getByText(/two recorded answers/i)).toBeInTheDocument()
  expect(screen.getByText(/Cee Andidate/)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /edit details/i })).toBeInTheDocument()
})

test('Start Test stays disabled until the mic consent is given', async () => {
  const user = userEvent.setup()
  renderGate()
  const btn = screen.getByRole('button', { name: /start test/i })
  expect(btn).toBeDisabled()
  await user.click(screen.getByRole('checkbox'))
  await waitFor(() => expect(btn).toBeEnabled())
})

test('consenting and clicking Start Test calls onBegin', async () => {
  const user = userEvent.setup()
  const onBegin = vi.fn().mockResolvedValue()
  renderGate({ onBegin })
  await user.click(screen.getByRole('checkbox'))
  await user.click(screen.getByRole('button', { name: /start test/i }))
  await waitFor(() => expect(onBegin).toHaveBeenCalledTimes(1))
})