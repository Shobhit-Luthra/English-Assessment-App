export class ApiError extends Error {
  constructor(status, path, body) {
    super(`${status} ${path}: ${body}`)
    this.status = status
  }
}

async function request(path, options = {}) {
  const res = await fetch(path, { credentials: 'include', ...options })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    if (res.status === 401) window.dispatchEvent(new CustomEvent('auth:logout'))
    throw new ApiError(res.status, path, body)
  }
  if (res.status === 204) return null
  return res.json()
}

const json = (method, body) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

// --- auth ---
export const signup = (b) => request('/api/auth/signup', json('POST', b))
export const login = (b) => request('/api/auth/login', json('POST', b))
export const logout = () => request('/api/auth/logout', { method: 'POST' })
export const getMe = () => request('/api/auth/me')

// --- candidate ---
export const putProfile = (b) => request('/api/candidate/profile', json('PUT', b))
export const getMyAttempts = () => request('/api/me/attempts')

// --- admin ---
export const adminListUsers = () => request('/api/admin/users')
export const adminCreateUser = (b) => request('/api/admin/users', json('POST', b))
export const adminPatchUser = (id, b) => request(`/api/admin/users/${id}`, json('PATCH', b))
export const adminListRoles = () => request('/api/admin/roles')
export const adminCreateRole = (b) => request('/api/admin/roles', json('POST', b))
export const adminPatchRole = (id, b) => request(`/api/admin/roles/${id}`, json('PATCH', b))
export const adminDeleteRole = (id) => request(`/api/admin/roles/${id}`, { method: 'DELETE' })
export const adminListPermissions = () => request('/api/admin/permissions')

// --- attempts (unchanged behaviour, now credentialed) ---
export const getAttemptItems = (attemptId) => request(`/api/attempts/${attemptId}/items`)
export const createAttempt = () => request('/api/attempts', json('POST', {}))
export const submitResponse = (attemptId, itemId, text) =>
  request(`/api/attempts/${attemptId}/response`, json('POST', { item_id: itemId, text }))
export const submitAttempt = (attemptId) =>
  request(`/api/attempts/${attemptId}/submit`, { method: 'POST' })
export const getReport = (attemptId) => request(`/api/attempts/${attemptId}/report`)
export const listAttempts = () => request('/api/attempts')

export async function uploadAudio(attemptId, itemId, blob, mimeType) {
  const ext = mimeType.includes('webm') ? 'webm' : 'mp4'
  const form = new FormData()
  form.append('item_id', itemId)
  form.append('file', blob, `${itemId}.${ext}`)
  const res = await fetch(`/api/attempts/${attemptId}/audio`, {
    method: 'POST', body: form, credentials: 'include',
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    if (res.status === 401) window.dispatchEvent(new CustomEvent('auth:logout'))
    throw new ApiError(res.status, 'audio upload', body)
  }
  return res.json()
}

// Objective sections score synchronously, but audio transcription + the LLM
// judge run in the background - normally ~15-30s, but the first submit after a
// cold start also pays a one-time Whisper model download, which can take
// several minutes. Cap generously (5 min) and tolerate a few transient fetch
// failures rather than aborting the whole attempt on one blip.
export async function pollReport(attemptId, { intervalMs = 2000, timeoutMs = 300000 } = {}) {
  const deadline = Date.now() + timeoutMs
  let consecutiveErrors = 0
  for (;;) {
    try {
      const report = await getReport(attemptId)
      consecutiveErrors = 0
      if (report.status !== 'scoring') return report
    } catch (err) {
      if (++consecutiveErrors >= 5) throw err
    }
    if (Date.now() >= deadline) {
      throw new Error('Scoring is taking longer than expected.')
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs))
  }
}
