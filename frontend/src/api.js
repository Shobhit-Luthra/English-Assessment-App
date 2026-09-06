async function request(path, options) {
  const res = await fetch(path, options)
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status} ${path}: ${body}`)
  }
  return res.json()
}

export function getItems() {
  return request('/api/items')
}

export function createAttempt(name) {
  return request('/api/attempts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
}

export function submitResponse(attemptId, itemId, text) {
  return request(`/api/attempts/${attemptId}/response`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ item_id: itemId, text }),
  })
}

export async function uploadAudio(attemptId, itemId, blob, mimeType) {
  const ext = mimeType.includes('webm') ? 'webm' : 'mp4'
  const form = new FormData()
  form.append('item_id', itemId)
  form.append('file', blob, `${itemId}.${ext}`)
  const res = await fetch(`/api/attempts/${attemptId}/audio`, { method: 'POST', body: form })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status} audio upload: ${body}`)
  }
  return res.json()
}

export function submitAttempt(attemptId) {
  return request(`/api/attempts/${attemptId}/submit`, { method: 'POST' })
}

export function getReport(attemptId) {
  return request(`/api/attempts/${attemptId}/report`)
}

export function listAttempts() {
  return request('/api/attempts')
}
