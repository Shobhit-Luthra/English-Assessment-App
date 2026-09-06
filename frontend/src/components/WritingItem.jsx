function countWords(text) {
  const trimmed = text.trim()
  return trimmed === '' ? 0 : trimmed.split(/\s+/).length
}

export default function WritingItem({ item, value, onAnswer }) {
  const wordCount = countWords(value || '')

  return (
    <div className="flex flex-col gap-4 text-left">
      <p className="text-lg font-medium">{item.prompt}</p>
      <textarea
        value={value || ''}
        onChange={(e) => onAnswer(e.target.value)}
        rows={8}
        className="w-full rounded-lg border border-gray-300 p-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
        placeholder="Type your reply here..."
      />
      <div className="text-sm text-gray-500">
        {wordCount} / {item.word_target} words
      </div>
    </div>
  )
}
