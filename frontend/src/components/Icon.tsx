import type { Section } from '../config'

// Small line icons, drawn inline so we don't need an icon library yet.
const PATHS: Record<Section['icon'], string> = {
  dashboard: 'M4 4h7v7H4zM13 4h7v4h-7zM13 10h7v10h-7zM4 13h7v7H4z',
  watchlist: 'M12 4l2.4 5 5.4.6-4 3.7 1.1 5.4L12 16l-4.9 2.7 1.1-5.4-4-3.7 5.4-.6z',
  compare: 'M8 4v16M16 4v16M4 8h8M12 16h8',
  movements: 'M3 17l5-6 4 3 5-7 4 4',
  profile: 'M12 12a4 4 0 100-8 4 4 0 000 8zM4 20c1.5-3.5 4.5-5 8-5s6.5 1.5 8 5',
}

export function Icon({ name }: { name: Section['icon'] }) {
  return (
    <svg
      className="icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={PATHS[name]} />
    </svg>
  )
}
