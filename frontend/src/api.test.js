import { afterEach, expect, test, vi } from 'vitest'
import { createAttempt, getAttemptItems } from './api'

afterEach(() => vi.restoreAllMocks())

test('getAttemptItems calls the per-attempt items path', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: true,
    json: async () => ({ items: [] }),
  })
  await getAttemptItems('abc-123')
  expect(fetchMock).toHaveBeenCalledWith('/api/attempts/abc-123/items', undefined)
})

test('createAttempt posts the name', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: true,
    json: async () => ({ attempt_id: 'x' }),
  })
  await createAttempt('Ada')
  const [, opts] = fetchMock.mock.calls[0]
  expect(JSON.parse(opts.body)).toEqual({ name: 'Ada' })
})
