import { Link } from 'react-router-dom'

const SECTIONS = [
  ['Grammar & Listening', 'Multiple-choice questions that measure accuracy and understanding.'],
  ['Writing', 'A short situational response, judged on tone and appropriateness.'],
  ['Speaking', 'Two recorded answers, transcribed and analyzed for fluency, pace and phrasing.'],
  ['Recommendation (CIR)', 'A single band from 1 to 6 that ties every section into one clear signal.'],
]

const STEPS = [
  ['1', 'Create your profile', 'Sign up and confirm your details in under a minute. No CV needed.'],
  ['2', 'Take the assessment', 'Four timed sections in a single sitting of about 15 minutes.'],
  ['3', 'See results and decisions', 'Get your scores instantly, plus a recommendation band and clear next steps.'],
]

const FAQ = [
  ['How long does the test take?', 'The whole assessment takes about 15 minutes. Speaking sections are recorded, so find a quiet space with a working microphone.'],
  ['How are the scores computed?', 'Each section is scored against a fixed 6-point rubric. Spoken answers are transcribed with speech-to-text and judged by a language model for fluency, phrasing and pace.'],
  ['Who can see my results?', 'You can always see your own scores. Recruiters linked to your assessment can view a report and record a hire or reject decision. Administrators manage accounts and roles.'],
  ['Can I take the test again?', 'Yes. You can start a new attempt whenever you are ready, and you will see a history of every attempt.'],
]

function Faq({ q, a }) {
  return (
    <details className="group border rounded-lg px-4 py-3">
      <summary className="flex cursor-pointer items-center justify-between text-sm font-medium">
        {q}
        <span
          aria-hidden="true"
          className="text-gray-400 group-open:hidden"
        >
          +
        </span>
      </summary>
      <p className="mt-2 text-sm text-gray-600 leading-relaxed">{a}</p>
    </details>
  )
}

export default function Landing() {
  return (
    <div className="min-h-screen bg-white text-gray-900">
      <header className="sticky top-0 z-20 bg-white border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <span className="font-semibold">English Assessment</span>
          <nav className="hidden sm:flex items-center gap-5 text-sm text-gray-600">
            <a href="#how-it-works" className="hover:text-gray-900">How it works</a>
            <a href="#sections" className="hover:text-gray-900">Sections</a>
            <a href="#recruiters" className="hover:text-gray-900">For recruiters</a>
            <a href="#faq" className="hover:text-gray-900">FAQ</a>
          </nav>
          <div className="flex items-center gap-3">
            <Link to="/login" className="text-sm font-medium text-gray-600 hover:text-gray-900">
              Sign in
            </Link>
            <Link
              to="/signup"
              className="rounded-lg bg-blue-700 text-white text-sm font-medium px-4 py-2 hover:bg-blue-800"
            >
              Get started
            </Link>
          </div>
        </div>
      </header>

      <section className="border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-6 py-20 flex flex-col items-center text-center gap-6">
          <h1 className="text-4xl font-semibold tracking-tight">
            A better way to evaluate
            <br />
            English proficiency
          </h1>
          <p className="max-w-2xl text-lg text-gray-600 leading-relaxed">
            Candidates take a short, four-section assessment. Recruiters get one
            recommendation score, a per-section breakdown, and a clear hire or
            reject decision. No guesswork, no lengthy interviews.
          </p>
          <div className="flex items-center gap-4">
            <Link
              to="/signup"
              className="rounded-lg bg-blue-700 text-white font-medium px-6 py-3 hover:bg-blue-800"
            >
              Start your first assessment
            </Link>
            <a
              href="#how-it-works"
              className="rounded-lg border border-gray-300 font-medium px-6 py-3 text-gray-700 hover:bg-gray-50"
            >
              See how it works
            </a>
          </div>
          <p className="text-sm text-gray-400">
            A single sitting of about 15 minutes, with sections run in order.
          </p>
        </div>
      </section>

      <section className="border-b border-gray-200 bg-gray-50">
        <div className="max-w-6xl mx-auto px-6 py-10 grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-gray-200">
          {[
            ['4', 'sections', 'grammar, listening, writing and speaking'],
            ['6', 'point scale', 'a single recommendation band (CIR)'],
            ['15 min', 'average', 'one sitting, timed end to end'],
          ].map(([big, small, text]) => (
            <div key={text} className="px-6 py-4 sm:text-center">
              <div className="text-3xl font-semibold text-blue-800">{big}</div>
              <div className="mt-1 text-sm font-medium text-gray-800">{small}</div>
              <div className="mt-1 text-sm text-gray-500">{text}</div>
            </div>
          ))}
        </div>
      </section>

      <section id="how-it-works" className="border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-6 py-20">
          <h2 className="text-3xl font-semibold">How it works</h2>
          <div className="mt-10 grid grid-cols-1 sm:grid-cols-3 gap-10">
            {STEPS.map(([num, title, text]) => (
              <div key={num} className="flex flex-col gap-3">
                <div className="h-10 w-10 flex items-center justify-center rounded-full border border-blue-700 text-blue-800 font-semibold">
                  {num}
                </div>
                <h3 className="text-lg font-medium">{title}</h3>
                <p className="text-sm text-gray-600 leading-relaxed">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="sections" className="border-b border-gray-200 bg-gray-50">
        <div className="max-w-6xl mx-auto px-6 py-20">
          <h2 className="text-3xl font-semibold">What the assessment covers</h2>
          <p className="mt-2 max-w-2xl text-gray-600">
            Every section is scored against a fixed rubric, so a result means the
            same thing for every candidate.
          </p>
          <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 gap-4">
            {SECTIONS.map(([title, text]) => (
              <div key={title} className="rounded-xl border bg-white p-6 flex flex-col gap-2">
                <h3 className="font-medium">{title}</h3>
                <p className="text-sm text-gray-600 leading-relaxed">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="recruiters" className="border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-6 py-20">
          <div className="rounded-2xl bg-blue-700 text-white p-10 sm:p-14 flex flex-col lg:flex-row lg:items-center gap-8">
            <div className="flex-1 flex flex-col gap-4">
              <h2 className="text-3xl font-semibold">Built for recruiters</h2>
              <p className="max-w-xl text-blue-100 leading-relaxed">
                Scan every candidate in one place: scores per section, a clear
                recommendation, and the ability to record a hire or reject
                decision your candidates can see.
              </p>
            </div>
            <div className="flex flex-col gap-3">
              {[
                'Candidate directory with latest scores',
                'Group analytics across all attempts',
                'Hire / reject workflow with sign-off',
              ].map((item) => (
                <div key={item} className="rounded-lg bg-white/10 px-4 py-3 text-sm">
                  {item}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section id="faq" className="border-b border-gray-200 bg-gray-50">
        <div className="max-w-3xl mx-auto px-6 py-20">
          <h2 className="text-3xl font-semibold mb-8">Frequently asked questions</h2>
          <div className="flex flex-col gap-3">
            {FAQ.map(([q, a]) => (
              <Faq key={q} q={q} a={a} />
            ))}
          </div>
        </div>
      </section>

      <footer className="bg-white">
        <div className="max-w-6xl mx-auto px-6 py-10 flex flex-col sm:flex-row justify-between gap-8">
          <div className="flex flex-col gap-1">
            <span className="font-semibold">English Assessment</span>
            <span className="text-sm text-gray-500">Interview-grade English proficiency scoring</span>
          </div>
          <div className="flex gap-10 text-sm text-gray-600">
            <div className="flex flex-col gap-2">
              <span className="font-medium text-gray-800">Product</span>
              <a href="#how-it-works" className="hover:text-gray-900">How it works</a>
              <a href="#sections" className="hover:text-gray-900">Sections</a>
              <a href="#recruiters" className="hover:text-gray-900">For recruiters</a>
            </div>
            <div className="flex flex-col gap-2">
              <span className="font-medium text-gray-800">Account</span>
              <Link to="/signup" className="hover:text-gray-900">Sign up</Link>
              <Link to="/login" className="hover:text-gray-900">Sign in</Link>
            </div>
          </div>
        </div>
        <div className="border-t border-gray-200">
          <div className="max-w-6xl mx-auto px-6 py-4 text-xs text-gray-400">
            © 2026 English Assessment. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  )
}