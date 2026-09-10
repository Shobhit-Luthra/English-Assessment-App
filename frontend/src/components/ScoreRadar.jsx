import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from 'recharts'

const AXIS_LABELS = {
  grammar: 'Grammar',
  listening: 'Listening',
  speaking_fluency: 'Speaking Fluency',
  writing_tone: 'Writing Tone',
  situational_task_fulfilment: 'Task Fulfilment',
}

export default function ScoreRadar({ bandsByDimension }) {
  const data = Object.entries(AXIS_LABELS).map(([key, label]) => ({
    dimension: label,
    band: bandsByDimension[key] ?? 0,
  }))

  return (
    <div className="w-full h-72">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} outerRadius="75%">
          <PolarGrid />
          <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 12 }} />
          <PolarRadiusAxis domain={[0, 6]} tickCount={7} axisLine={false} tick={{ fontSize: 10 }} />
          <Radar
            dataKey="band"
            stroke="#9333ea"
            fill="#9333ea"
            fillOpacity={0.35}
            isAnimationActive={false}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}
