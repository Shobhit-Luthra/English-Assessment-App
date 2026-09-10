import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import Analytics from './Analytics'

vi.mock('../api', () => ({ fetchAnalytics: vi.fn() }))
import { fetchAnalytics } from '../api'

afterEach(() => vi.clearAllMocks())

const SAMPLE = {
  total_candidates_tested: 2,
  total_attempts: 3,
  completed_attempts: 2,
  in_progress_attempts: 1,
  cir: { average: 4.0, recommended: 1, borderline: 0, not_recommended: 1, pass_rate: 0.5 },
  benchmarks: { median: 4.0, top_25: 4.5 },
  sections: { understanding: 3.75, grammar: 4.0, listening: 4.0, speaking: 4.0, writing: 6.0, task_fulfilment: 4.0 },
  decisions: { hired: 1, rejected: 1, pending: 0, total: 2 },
}

test('renders headline stats and section averages', async () => {
  fetchAnalytics.mockResolvedValue(SAMPLE)
  render(<Analytics />)
  await waitFor(() => expect(screen.getByText(/candidates tested/i)).toBeInTheDocument())
  expect(screen.getAllByText('2').length).toBeGreaterThanOrEqual(2) // tested + completed
  expect(screen.getAllByText('4').length).toBeGreaterThanOrEqual(1) // average CIR + median benchmark
  expect(screen.getByText('50%')).toBeInTheDocument() // recommended rate
  expect(screen.getByText(/average score by section/i)).toBeInTheDocument()
  expect(screen.getByText('Understanding')).toBeInTheDocument()
  expect(screen.getByText('6 / 6')).toBeInTheDocument()
})

test('shows benchmark percentiles', async () => {
  fetchAnalytics.mockResolvedValue(SAMPLE)
  render(<Analytics />)
  await waitFor(() => expect(screen.getByText(/candidate benchmarks/i)).toBeInTheDocument())
  expect(screen.getByText('Typical score:')).toBeInTheDocument()
  expect(screen.getByText('Top 25% score at least:')).toBeInTheDocument()
})

test('shows the decision and recommendation distribution', async () => {
  fetchAnalytics.mockResolvedValue(SAMPLE)
  render(<Analytics />)
  await waitFor(() => expect(screen.getByText(/recommendation spread/i)).toBeInTheDocument())
  expect(screen.getAllByText(/recommended:/i).length).toBeGreaterThanOrEqual(1)
  expect(screen.getByText(/not recommended:/i)).toBeInTheDocument()
  expect(screen.getByText(/hired:/i)).toBeInTheDocument()
  expect(screen.getByText(/rejected:/i)).toBeInTheDocument()
})

test('shows an empty state when nobody has completed a test', async () => {
  fetchAnalytics.mockResolvedValue({ ...SAMPLE, completed_attempts: 0, benchmarks: { median: null, top_25: null }, cir: { ...SAMPLE.cir, average: null, pass_rate: null } })
  render(<Analytics />)
  await waitFor(() => expect(screen.getByText(/no completed attempts yet/i)).toBeInTheDocument())
})
