import '@testing-library/jest-dom/vitest'

if (typeof globalThis.MediaRecorder === 'undefined') {
  class MediaRecorder {
    static isTypeSupported() {
      return true
    }
  }
  globalThis.MediaRecorder = MediaRecorder
}
