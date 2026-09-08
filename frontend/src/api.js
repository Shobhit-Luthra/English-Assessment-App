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

export function listAttempts() {
  return request('/api/attempts')
}
