const LETTERS = ['a', 'b', 'c', 'd']

export default function McqItem({ item, value, onAnswer }) {
  return (
    <div className="flex flex-col gap-4 text-left">
      {item.audio && (
        // eslint-disable-next-line jsx-a11y/media-has-caption
        <audio controls src={item.audio} className="w-full">
          Your browser does not support audio playback.
        </audio>
      )}
      <p className="text-lg font-medium">{item.prompt}</p>
      <div className="flex flex-col gap-2">
        {item.options.map((option, idx) => {
          const letter = LETTERS[idx]
          const selected = value === letter
          return (
            <label
              key={letter}
              className={`flex items-center gap-3 rounded-lg border p-3 cursor-pointer transition ${
                selected ? 'border-blue-600 bg-blue-50' : 'border-gray-200'
              }`}
            >
              <input
                type="radio"
                name={item.id}
                value={letter}
                checked={selected}
                onChange={() => onAnswer(letter)}
                className="accent-blue-700"
              />
              <span>{option}</span>
            </label>
          )
        })}
      </div>
    </div>
  )
}
