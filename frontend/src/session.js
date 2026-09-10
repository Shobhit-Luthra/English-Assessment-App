const KEY = 'assessment.session'

export function saveSession(record) {
  try {
    localStorage.setItem(KEY, JSON.stringify(record))
  } catch {
    // storage unavailable (private mode / disabled) — resume is best-effort
  }
}

export function loadSession() {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed.attemptId !== 'string') return null
    return parsed
  } catch {
    return null
  }
}

export function clearSession() {
  try {
    localStorage.removeItem(KEY)
  } catch {
    // no-op
  }
}
