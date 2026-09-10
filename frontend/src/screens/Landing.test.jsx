import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { expect, test } from 'vitest'
import Landing from './Landing'

test('landing page shows the hero, the core pitch and calls-to-action', () => {
  render(
    <MemoryRouter>
      <Landing />
    </MemoryRouter>,
  )
  expect(screen.getByText(/a better way to evaluate/i)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /start your first assessment/i })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /get started/i })).toBeInTheDocument()
  expect(screen.getByText(/recommendation \(cir\)/i)).toBeInTheDocument()
  expect(screen.getByText(/built for recruiters/i)).toBeInTheDocument()
})

test('landing page links to sign in and sign up', () => {
  render(
    <MemoryRouter>
      <Landing />
    </MemoryRouter>,
  )
  expect(screen.getAllByRole('link', { name: /sign in/i }).length).toBeGreaterThan(0)
  expect(screen.getByRole('link', { name: /sign up/i })).toBeInTheDocument()
})