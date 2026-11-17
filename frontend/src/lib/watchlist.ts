import { createContext, useContext } from 'react'
import type { Game } from '../types/market'
import type { User } from './accountApi'

export interface SavedItem {
  item_name: string
  game: Game
  added_at: string
  added_price_minor: number | null
}

interface AccountState {
  user: User | null
  items: SavedItem[]
  busy: boolean
  error: string
  refresh: () => Promise<boolean>
  signIn: (email: string, password: string, register?: boolean) => Promise<boolean>
  signOut: () => Promise<boolean>
  has: (name: string, game: Game) => boolean
  add: (name: string, game: Game, price: number | null) => Promise<boolean>
  remove: (name: string, game: Game) => Promise<boolean>
}

export const AccountContext = createContext<AccountState | null>(null)

/** All pages consume the provider's account-owned list, not a browser-local copy. */
export function useWatchlist() {
  const context = useContext(AccountContext)
  if (!context) throw new Error('useWatchlist requires AccountProvider')
  return context
}
