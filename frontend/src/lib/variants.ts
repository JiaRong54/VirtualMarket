import type { Game } from '../types/market'

// Groups Steam item names into "the same skin in different versions".
//
// CS2:   "StatTrak™ AK-47 | Redline (Field-Tested)"
//          -> skin "AK-47 | Redline", variant "StatTrak™ Field-Tested"
// Dota 2: "Inscribed Dragonclaw Hook"
//          -> skin "Dragonclaw Hook", variant "Inscribed"

export interface ParsedName {
  skin: string // the name shared by every variant
  variant: string // what makes this one different, "Standard" if nothing
  order: number // sort key so variants list in a sensible order
}

// Wear from best to worst, the order players expect.
const WEARS = ['Factory New', 'Minimal Wear', 'Field-Tested', 'Well-Worn', 'Battle-Scarred']
const CS2_KINDS = ['StatTrak™', 'Souvenir']
// Dota 2 item qualities that show up as a prefix on the market name.
const DOTA_QUALITIES = [
  'Inscribed', 'Genuine', 'Heroic', 'Autographed', 'Exalted', 'Frozen', 'Corrupted',
  'Elder', 'Cursed', 'Unusual', 'Infused', 'Auspicious', 'Base',
]

const wearRe = new RegExp(` \\((${WEARS.join('|')})\\)$`)

export function parseName(name: string, game: Game): ParsedName {
  if (game === 'dota2') {
    const q = DOTA_QUALITIES.find((p) => name.startsWith(p + ' '))
    return q
      ? { skin: name.slice(q.length + 1), variant: q, order: DOTA_QUALITIES.indexOf(q) + 1 }
      : { skin: name, variant: 'Standard', order: 0 }
  }

  let rest = name
  const star = rest.startsWith('★ ') ? '★ ' : '' // knives and gloves keep their star in the skin name
  rest = rest.slice(star.length)

  const kind = CS2_KINDS.find((k) => rest.startsWith(k + ' ')) ?? ''
  if (kind) rest = rest.slice(kind.length + 1)

  const m = rest.match(wearRe)
  const wear = m ? m[1] : ''
  if (m) rest = rest.slice(0, m.index)

  const parts = [kind, wear].filter(Boolean)
  const wearIdx = wear ? WEARS.indexOf(wear) : 0
  const kindIdx = kind ? CS2_KINDS.indexOf(kind) + 1 : 0
  return {
    skin: star + rest,
    variant: parts.length ? parts.join(' ') : 'Standard',
    order: kindIdx * 10 + wearIdx,
  }
}

/** skin name -> its variants, keeping only skins that come in 2 or more versions. */
export function groupVariants<T extends { item_name: string }>(items: T[], game: Game) {
  const groups = new Map<string, (T & ParsedName)[]>()
  for (const item of items) {
    const parsed = parseName(item.item_name, game)
    const list = groups.get(parsed.skin) ?? []
    list.push({ ...item, ...parsed })
    groups.set(parsed.skin, list)
  }
  for (const [skin, list] of groups) {
    if (list.length < 2) groups.delete(skin)
    else list.sort((a, b) => a.order - b.order)
  }
  return groups
}
