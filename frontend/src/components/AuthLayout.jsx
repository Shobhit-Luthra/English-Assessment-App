export default function AuthLayout({ title, subtitle, footer, children }) {
  return (
    <div className="min-h-screen bg-gray-50 flex lg:flex-row flex-col">
      <aside className="lg:flex hidden w-[46%] bg-blue-700 text-white flex-col justify-between p-12">
        <p className="text-lg font-semibold">English Assessment</p>
        <div className="max-w-md flex flex-col gap-8">
          <h2 className="text-3xl font-semibold leading-tight">
            Interview-grade English proficiency scoring
          </h2>
          <p className="text-blue-100 text-sm leading-relaxed">
            Candidates take a short, four-section proficiency test. Recruiters get one
            recommendation score plus a breakdown of every section.
          </p>
          <ul className="flex flex-col gap-3 text-sm text-blue-50">
            <li>Grammar, listening, writing and speaking in a single sitting</li>
            <li>Speech-to-text transcription with an AI language-model judge</li>
            <li>A clear recommendation band per attempt (CIR)</li>
            <li>Hire / reject workflow built for recruiters</li>
          </ul>
        </div>
        <p className="text-xs text-blue-200">
          Role-based access for candidates, recruiters and administrators.
        </p>
      </aside>

      <div className="flex-1 flex flex-col items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <p className="lg:hidden text-lg font-semibold mb-8">English Assessment</p>
          <h1 className="text-2xl font-semibold">{title}</h1>
          {subtitle && <p className="text-sm text-gray-600 mt-1">{subtitle}</p>}
          <div className="mt-8">{children}</div>
        </div>
        {footer && (
          <p className="mt-10 text-xs text-gray-400">
            {footer}
          </p>
        )}
      </div>
    </div>
  )
}