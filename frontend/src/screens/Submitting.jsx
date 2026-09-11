export default function Submitting({ error, onRetry, engineOffline = false }) {
  if (error) {
    return (
      <div className="max-w-md mx-auto flex flex-col items-center gap-4 p-6 text-center">
        <p className="text-lg font-medium">Still scoring</p>
        <p className="text-sm text-gray-500">{error}</p>
        <button
          type="button"
          onClick={onRetry}
          className="rounded-lg bg-blue-700 text-white px-6 py-2 font-medium"
        >
          Check again
        </button>
      </div>
    )
  }

  if (engineOffline) {
    return (
      <div className="max-w-md mx-auto flex flex-col items-center gap-4 p-6 text-center">
        <p className="text-lg font-medium">The scoring engine is offline</p>
        <p className="text-sm text-gray-500">
          Your answers are saved, but scoring could not run right now. A recruiter can re-run it
          later, and your result will then appear under My results.
        </p>
      </div>
    )
  }

  return (
    <div className="max-w-md mx-auto flex flex-col items-center gap-4 p-6 text-center">
      <div className="h-10 w-10 rounded-full border-4 border-blue-200 border-t-blue-700 animate-spin" />
      <p className="text-lg font-medium">Scoring your responses</p>
      <p className="text-sm text-gray-500">
        This usually takes about 30 seconds. The first run after starting the server can take a few
        minutes while the speech model loads.
      </p>
      <p className="text-xs text-gray-400">Tip: keep this tab open while your test finishes scoring.</p>
    </div>
  )
}
