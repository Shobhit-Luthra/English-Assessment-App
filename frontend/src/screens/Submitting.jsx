export default function Submitting({ error, onRetry }) {
  if (error) {
    return (
      <div className="max-w-md mx-auto flex flex-col items-center gap-4 p-6 text-center">
        <p className="text-lg font-medium">Still scoring</p>
        <p className="text-sm text-gray-500">{error}</p>
        <button
          type="button"
          onClick={onRetry}
          className="rounded-lg bg-purple-600 text-white px-6 py-2 font-medium"
        >
          Check again
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-md mx-auto flex flex-col items-center gap-4 p-6 text-center">
      <div className="h-10 w-10 rounded-full border-4 border-purple-200 border-t-purple-600 animate-spin" />
      <p className="text-lg font-medium">Scoring your responses</p>
      <p className="text-sm text-gray-500">
        This usually takes about 30 seconds. The first run after starting the server can take a few
        minutes while the speech model loads.
      </p>
    </div>
  )
}
