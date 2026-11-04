// The sections of the app. The sidebar and the router both read from this
// list, so adding a section means adding one entry here and one page file.

export interface Section {
  path: string
  label: string
  icon: 'dashboard' | 'compare' | 'movements' | 'profile'
  blurb: string
}

export const SECTIONS: Section[] = [
  {
    path: '/',
    label: 'Dashboard',
    icon: 'dashboard',
    blurb: 'Market overview and the main price table',
  },
  {
    path: '/compare',
    label: 'Compare',
    icon: 'compare',
    blurb: 'Variants of the same skin, side by side',
  },
  {
    path: '/movements',
    label: 'Price Movements',
    icon: 'movements',
    blurb: 'Unusual moves, lined up against game updates',
  },
  {
    path: '/profile',
    label: 'Profile',
    icon: 'profile',
    blurb: 'Account and Steam settings',
  },
]

// Facts about the pipeline that are true today. Shown in the sidebar.
export const PIPELINE = {
  source: 'Steam Market',
  refresh: 'Latest observations',
  game: 'CS2',
}
