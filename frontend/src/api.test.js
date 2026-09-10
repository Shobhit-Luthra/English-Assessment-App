import { afterEach, expect, test, vi } from 'vitest'
import { ApiError, createAttempt, getAttemptItems, getMe, login } from './api'

afterEach(() => vi.restoreAllMocks())

test('getAttemptItems calls the per-attempt items path with credentials', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: true,
    json: async () => ({ items: [] }),
  })
  await getAttemptItems('abc-123')
  expect(fetchMock).toHaveBeenCalledWith(
    '/api/attempts/abc-123/items',
    expect.objectContaining({ credentials: 'include' }),
  )
})

test('createAttempt posts an empty body', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: true,
    json: async () => ({ attempt_id: 'x' }),
  })
  await createAttempt()
  const [, opts] = fetchMock.mock.calls[0]
  expect(JSON.parse(opts.body)).toEqual({})
})

test('getMe sends credentials', async () => {
  const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify({ email: 'a@b.com' }), { status: 200 }),
  )
  await getMe()
  expect(fetchSpy).toHaveBeenCalledWith(
    '/api/auth/me',
    expect.objectContaining({ credentials: 'include' }),
  )
})

test('a 401 dispatches auth:logout and throws ApiError', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('nope', { status: 401 }))
  const handler = vi.fn()
  window.addEventListener('auth:logout', handler)
  await expect(login({ email: 'x', password: 'y' })).rejects.toBeInstanceOf(ApiError)
  expect(handler).toHaveBeenCalled()
  window.removeEventListener('auth:logout', handler)
})
