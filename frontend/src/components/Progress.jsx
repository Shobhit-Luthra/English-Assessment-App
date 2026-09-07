const SECTION_ORDER = ['grammar', 'listening', 'writing', 'speaking']
const LABELS = { grammar: 'Grammar', listening: 'Listening', writing: 'Writing', speaking: 'Speaking' }

export default function Progress({ items, index }) {
  const currentSection = items[index]?.section
  const sections = SECTION_ORDER.filter((s) => items.some((it) => it.section === s))

  return (
    <ol className="flex flex-wrap items-center gap-2 text-xs" data-testid="progress">
      {sections.map((section) => {
        const inSection = items.filter((it) => it.section === section)
        const lastIdxOfSection = items.map((it) => it.section).lastIndexOf(section)
        const done = index > lastIdxOfSection
        const active = section === currentSection
        const posInSection = active
          ? items.slice(0, index + 1).filter((it) => it.section === section).length
          : null

        const classes = active
          ? 'bg-purple-600 text-white'
          : done
            ? 'bg-purple-100 text-purple-700'
            : 'bg-gray-100 text-gray-400'

        return (
          <li key={section} className={`rounded-full px-3 py-1 font-medium ${classes}`}>
            {done && !active ? '✓ ' : ''}
            {LABELS[section]}
            {active ? ` ${posInSection}/${inSection.length}` : ''}
          </li>
        )
      })}
    </ol>
  )
}
