async function request(path, options) {
  const res = await fetch(path, options)
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status} ${path}: ${body}`)
  }
  return res.json()
}

export function getAttemptItems(attemptId) {
  return request(`/api/attempts/${attemptId}/items`)
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

// Objective sections score synchronously, but audio transcription + the LLM
// judge run in the background (~15-30s) - poll until the pipeline leaves
// "scoring". Caps at ~90s so a stuck attempt surfaces as an error instead of
// polling forever.
export async function pollReport(attemptId, { intervalMs = 2000, timeoutMs = 90000 } = {}) {
  const deadline = Date.now() + timeoutMs
  for (;;) {
    const report = await getReport(attemptId)
    if (report.status !== 'scoring') return report
    if (Date.now() >= deadline) {
      throw new Error('Scoring is taking longer than expected.')
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs))
  }
}

export function listAttempts() {
  return request('/api/attempts')
}
