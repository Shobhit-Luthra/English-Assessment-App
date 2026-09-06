export default function Report({ report }) {
  return (
    <div className="max-w-md mx-auto flex flex-col gap-4 p-6">
      <h1 className="text-2xl font-semibold">{report.name}'s Report</h1>
      <p className="text-sm text-gray-500">Status: {report.status}</p>
      <div className="flex flex-col gap-2">
        {report.scores.map((s) => (
          <div key={s.dimension} className="flex items-center justify-between border-b py-2">
            <span className="capitalize">{s.dimension}</span>
            <span className="font-mono text-lg">{s.band} / 6</span>
          </div>
        ))}
      </div>
    </div>
  )
}
