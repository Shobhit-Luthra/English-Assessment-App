import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import Report from './Report'

vi.mock('../components/ScoreRadar', () => ({
  default: ({ bandsByDimension }) => (
    <div data-testid="radar">{Object.keys(bandsByDimension).join(',')}</div>
  ),
}))

const features = {
  speech_rate: 120, phonation_ratio: 0.6, mean_length_of_run: 6, pauses_per_100w: 3,
  filled_pause_rate: 0,
}

function fullReport() {
  return {
    attempt_id: 'a1',
    name: 'Alice',
    status: 'done',
    error: null,
    error_message: null,
    scores: [
      { dimension: 'grammar', band: 6, evidence: { correct: 4, total: 4 } },
      { dimension: 'listening', band: 4, evidence: { correct: 1, total: 2 } },
      {
        dimension: 'speaking_fluency_s1', band: 5, audio_url: '/audio/a1/s1.webm',
        evidence: { item_id: 's1', item_type: 'read_aloud', transcript: 'thank you', features, wer: 0.1 },
      },
      {
        dimension: 'speaking_fluency_s2', band: 4, audio_url: '/audio/a1/s2.webm',
        evidence: {
          item_id: 's2', item_type: 'situational', transcript: 'first you', features,
          justification: 'Clear.',
          scores: { fluency: 4, grammar: 3, vocabulary: 5, task_fulfilment: 4 },
        },
      },
      { dimension: 'situational_task_fulfilment', band: 4, evidence: { item_id: 's2' } },
      {
        dimension: 'writing_tone', band: 5, response_text: 'Dear customer',
        evidence: {
          item_id: 'w1', justification: 'Polite.',
          scores: { grammar: 4, vocabulary: 5, tone_appropriateness: 5, task_fulfilment: 3 },
        },
      },
      { dimension: 'speaking', band: 4, evidence: { components: [4] } },
      { dimension: 'writing', band: 4, evidence: { components: [4.25] } },
      { dimension: 'cir', band: 4, evidence: {} },
    ],
  }
}

test('shows every judged sub-skill for speaking and writing', () => {
  render(<Report report={fullReport()} />)
  const speaking = screen.getByTestId('subskills-s2')
  expect(speaking).toHaveTextContent(/Fluency\s*4/)
  expect(speaking).toHaveTextContent(/Grammar\s*3/)
  expect(speaking).toHaveTextContent(/Vocabulary\s*5/)
  expect(speaking).toHaveTextContent(/Task\s*4/)
  const writing = screen.getByTestId('subskills-w1')
  expect(writing).toHaveTextContent(/Tone\s*5/)
  expect(writing).toHaveTextContent(/Task\s*3/)
  expect(screen.getByRole('heading', { name: /^writing$/i })).toBeInTheDocument()
})

test('radar plots the composite sections the recruiter view uses', () => {
  render(<Report report={fullReport()} />)
  expect(screen.getByTestId('radar')).toHaveTextContent(
    'grammar,listening,speaking,writing,task_fulfilment',
  )
})

test('marks a skipped item as not attempted instead of scoring it', () => {
  const report = fullReport()
  report.scores = report.scores.map((s) =>
    s.dimension === 'speaking_fluency_s2'
      ? { dimension: s.dimension, band: 1, audio_url: null, evidence: { item_id: 's2', item_type: 'situational', missing: true } }
      : s,
  )
  render(<Report report={report} />)
  expect(screen.getByText(/not attempted/i)).toBeInTheDocument()
  expect(screen.queryByTestId('subskills-s2')).not.toBeInTheDocument()
})

test('failed attempt shows the safe message and no re-score button for candidates', () => {
  const report = { ...fullReport(), status: 'error', error: 'judge_unavailable',
    error_message: 'The scoring engine was unavailable.', scores: [] }
  render(<Report report={report} />)
  expect(screen.getByText(/scoring engine was unavailable/i)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /re-score/i })).not.toBeInTheDocument()
})

test('failed attempt offers re-score when the viewer may re-run it', async () => {
  const onRescore = vi.fn()
  const report = { ...fullReport(), status: 'error', error: 'judge_unavailable',
    error_message: 'The scoring engine was unavailable.', scores: [] }
  render(<Report report={report} onRescore={onRescore} />)
  await userEvent.click(screen.getByRole('button', { name: /re-score/i }))
  expect(onRescore).toHaveBeenCalledTimes(1)
})
