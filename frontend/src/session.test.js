import { afterEach, expect, test } from 'vitest'
import { clearSession, loadSession, saveSession } from './session'

afterEach(() => localStorage.clear())

test('save then load round-trips', () => {
  saveSession({ attemptId: 'a1', index: 3 })
  expect(loadSession()).toEqual({ attemptId: 'a1', index: 3 })
})

test('loadSession returns null when nothing stored', () => {
  expect(loadSession()).toBeNull()
})

test('loadSession returns null on corrupt data', () => {
  localStorage.setItem('assessment.session', '{not json')
  expect(loadSession()).toBeNull()
})

test('loadSession returns null when attemptId is not a string', () => {
  localStorage.setItem('assessment.session', JSON.stringify({ attemptId: 42, index: 0 }))
  expect(loadSession()).toBeNull()
})

test('clearSession removes the record', () => {
  saveSession({ attemptId: 'a1', index: 1 })
  clearSession()
  expect(loadSession()).toBeNull()
})
