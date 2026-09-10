import ScoreRadar from '../components/ScoreRadar'

// Fixed thresholds for the recommendation banner. Not specified numerically
// by the PRD beyond "against a fixed threshold" - chosen so band 4 (the
// rubric's "adequate for the task, generally appropriate" tier) reads as
// borderline rather than an automatic pass.
function recommendation(band) {
  if (band >= 5) return { label: 'Recommended', className: 'bg-green-100 text-green-800' }
  if (band === 4) return { label: 'Borderline', className: 'bg-yellow-100 text-yellow-800' }
  return { label: 'Not Recommended', className: 'bg-red-100 text-red-800' }
}

function ScoreBar({ label, value, total }) {
  return (
    <div className="flex items-center justify-between border-b py-2">
      <span>{label}</span>
      <span className="font-mono text-sm text-gray-500">
        {value} / {total} correct
      </span>
    </div>
  )
}

const SPEAKING_LABELS = {
  read_aloud: 'Read Aloud',
  situational: 'Situational',
}

function bandBadgeClass(band) {
  if (band >= 5) return 'bg-green-100 text-green-800'
  if (band === 4) return 'bg-yellow-100 text-yellow-800'
  return 'bg-red-100 text-red-800'
}

function Stat({ label, value }) {
  return (
    <span className="rounded-md border border-gray-200 px-2 py-1 text-xs text-gray-600">
      <span className="text-gray-400">{label}:</span> {value}
    </span>
  )
}

function SpeakingCard({ score }) {
  const { evidence, band, audio_url: audioUrl } = score
  const title = SPEAKING_LABELS[evidence.item_type] || 'Speaking'
  const section = evidence.item_id?.toUpperCase()
  const features = evidence.features

  return (
    <div className="flex flex-col gap-3 rounded-lg border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h3 className="font-medium">{title}</h3>
          {section && (
            <span className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-xs text-gray-500">
              {section}
            </span>
          )}
        </div>
        <span className={`rounded-full px-3 py-1 font-mono text-sm ${bandBadgeClass(band)}`}>
          Band {band} / 6
        </span>
      </div>

      {audioUrl && (
        // eslint-disable-next-line jsx-a11y/media-has-caption
        <audio controls src={audioUrl} className="w-full" />
      )}

      {evidence.transcript && (
        <div className="rounded-md bg-gray-50 p-3">
          <p className="mb-1 text-xs font-medium text-gray-500">What was said</p>
          <p className="text-sm text-gray-700">{evidence.transcript}</p>
        </div>
      )}

      {evidence.reference_text && (
        <div className="rounded-md border border-dashed border-gray-300 p-3">
          <p className="mb-1 text-xs font-medium text-gray-500">
            Expected (read aloud)
          </p>
          <p className="text-sm text-gray-500">{evidence.reference_text}</p>
        </div>
      )}

      {evidence.justification && (
        <p className="text-sm text-gray-800">{evidence.justification}</p>
      )}

      {features && (
        <div className="flex flex-wrap gap-2">
          {features.speech_rate !== undefined && (
            <Stat label="Speech rate" value={`${features.speech_rate.toFixed(0)} wpm`} />
          )}
          {features.phonation_ratio !== undefined && (
            <Stat label="Voice activity" value={`${Math.round(features.phonation_ratio * 100)}%`} />
          )}
          {features.mean_length_of_run !== undefined && (
            <Stat label="Avg. run" value={`${features.mean_length_of_run.toFixed(1)} words`} />
          )}
          {features.pauses_per_100w !== undefined && (
            <Stat label="Pauses" value={`${features.pauses_per_100w.toFixed(1)} / 100 words`} />
          )}
          {evidence.wer !== undefined && (
            <Stat label="Word error rate" value={`${(evidence.wer * 100).toFixed(0)}%`} />
          )}
        </div>
      )}
    </div>
  )
}

export default function Report({ report }) {
  const byDim = Object.fromEntries(report.scores.map((s) => [s.dimension, s]))
  const speakingScores = report.scores
    .filter((s) => s.dimension.startsWith('speaking_fluency_'))
    .sort((a, b) => a.evidence.item_id.localeCompare(b.evidence.item_id))

  const cir = byDim.cir
  const rec = cir ? recommendation(cir.band) : null

  const speakingFluencyAvg = speakingScores.length
    ? speakingScores.reduce((sum, s) => sum + s.band, 0) / speakingScores.length
    : 0

  const radarBands = {
    grammar: byDim.grammar?.band ?? 0,
    listening: byDim.listening?.band ?? 0,
    speaking_fluency: speakingFluencyAvg,
    writing_tone: byDim.writing_tone?.band ?? 0,
    situational_task_fulfilment: byDim.situational_task_fulfilment?.band ?? 0,
  }

  const writing = byDim.writing_tone

  if (report.status === 'scoring') {
    return (
      <div className="max-w-md mx-auto p-6 text-center text-gray-600">
        Still scoring - refresh in a moment.
      </div>
    )
  }

  if (report.status === 'error') {
    return (
      <div className="max-w-md mx-auto p-6 text-center text-red-600">
        Scoring failed: {report.error || 'unknown error'}
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto flex flex-col gap-8 p-6">
      <div className="flex flex-col items-center gap-3 text-center">
        <div>
          <h1 className="text-2xl font-semibold">{report.name}'s Report</h1>
          <p className="mt-1 font-mono text-xs text-gray-400">Attempt {report.attempt_id}</p>
        </div>
        {cir && (
          <>
            <div className="text-5xl font-bold text-blue-800">{cir.band} / 6</div>
            {rec && (
              <span className={`rounded-full px-4 py-1 text-sm font-medium ${rec.className}`}>
                {rec.label}
              </span>
            )}
            <p className="text-xs text-gray-500">
              {cir.band >= 5
                ? 'Recommended - meets the passing band.'
                : cir.band === 4
                  ? 'Borderline - review the details below.'
                  : 'Not recommended - below the passing band.'}
            </p>
          </>
        )}
      </div>

      <ScoreRadar bandsByDimension={radarBands} />

      {(byDim.grammar || byDim.listening) && (
        <section className="flex flex-col gap-2">
          <h2 className="text-lg font-semibold">Grammar &amp; Listening</h2>
          {byDim.grammar && (
            <ScoreBar
              label="Grammar"
              value={byDim.grammar.evidence.correct}
              total={byDim.grammar.evidence.total}
            />
          )}
          {byDim.listening && (
            <ScoreBar
              label="Listening"
              value={byDim.listening.evidence.correct}
              total={byDim.listening.evidence.total}
            />
          )}
        </section>
      )}

      {speakingScores.length > 0 && (
        <section className="flex flex-col gap-4">
          <h2 className="text-lg font-semibold">Speaking</h2>
          {speakingScores.map((s) => (
            <SpeakingCard key={s.dimension} score={s} />
          ))}
        </section>
      )}

      {writing && (
        <section className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold">Writing</h2>
          <div className="rounded-lg border p-4 flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="font-medium">Tone Appropriateness</span>
              <span className="font-mono text-lg">{writing.band} / 6</span>
            </div>
            {writing.response_text && (
              <p className="text-sm text-gray-600 whitespace-pre-wrap">{writing.response_text}</p>
            )}
            {writing.evidence.justification && (
              <p className="text-sm text-gray-800">{writing.evidence.justification}</p>
            )}
          </div>
        </section>
      )}
    </div>
  )
}
