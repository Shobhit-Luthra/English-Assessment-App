import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import Progress from './Progress'

const items = [
  { id: 'g1', section: 'grammar' }, { id: 'g2', section: 'grammar' },
  { id: 'l1', section: 'listening' },
  { id: 'w1', section: 'writing' },
  { id: 's1', section: 'speaking' }, { id: 's2', section: 'speaking' },
]

test('shows all four section labels', () => {
  render(<Progress items={items} index={0} />)
  for (const label of ['Grammar', 'Listening', 'Writing', 'Speaking']) {
    expect(screen.getByText(new RegExp(label))).toBeInTheDocument()
  }
})

test('marks the current section with position within it', () => {
  render(<Progress items={items} index={1} />)
  expect(screen.getByText(/Grammar 2\/2/)).toBeInTheDocument()
})

test('current section is on the speaking chip when index is in speaking', () => {
  render(<Progress items={items} index={4} />)
  expect(screen.getByText(/Speaking 1\/2/)).toBeInTheDocument()
})
