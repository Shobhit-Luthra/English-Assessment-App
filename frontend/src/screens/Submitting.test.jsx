import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import Submitting from './Submitting'

test('tells the candidate when the scoring engine is offline', () => {
  render(<Submitting engineOffline />)
  expect(screen.getByText(/scoring engine is offline/i)).toBeInTheDocument()
  expect(screen.getByText(/answers are saved/i)).toBeInTheDocument()
  expect(screen.queryByText(/once the engine is back/i)).not.toBeInTheDocument()
  expect(screen.getByText(/recruiter can re-run/i)).toBeInTheDocument()
})

test('shows the normal wait message when the engine is up', () => {
  render(<Submitting />)
  expect(screen.getByText(/scoring your responses/i)).toBeInTheDocument()
  expect(screen.queryByText(/offline/i)).not.toBeInTheDocument()
})
