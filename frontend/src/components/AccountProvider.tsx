import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import type { Game } from '../types/market'
import { AccountApiError, accountRequest } from '../lib/accountApi'
import type { User } from '../lib/accountApi'
import { AccountContext } from '../lib/watchlist'
import type { SavedItem } from '../lib/watchlist'
const same = (item: SavedItem, name: string, game: Game) => item.item_name === name && item.game === game

/** One shared account/list for Profile, Watchlist and item pages. */
export function AccountProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [items, setItems] = useState<SavedItem[]>([])
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')
  const locked = useRef(false)
  const channel = useRef<BroadcastChannel | null>(null)
  const pendingRefresh = useRef(false)

  function clearAccount() {
    setUser(null)
    setItems([])
  }

  async function loadAccount() {
    const data = await accountRequest<{ user: User; items: SavedItem[] }>('/watchlist')
    setUser(data.user)
    setItems(data.items)
  }

  /** Serialize operations and keep failed saves visible instead of pretending success. */
  async function run(action: () => Promise<void>, sessionCheck = false): Promise<boolean> {
    if (locked.current) return false
    locked.current = true
    setBusy(true)
    setError('')
    try {
      await action()
      return true
    } catch (err) {
      if (err instanceof AccountApiError && err.status === 401) {
        clearAccount()
        if (!sessionCheck) setError(err.message)
      } else {
        if (err instanceof AccountApiError && err.status === 409) clearAccount()
        setError(err instanceof Error ? err.message : 'Unable to connect. Please try again.')
      }
      return false
    } finally {
      locked.current = false
      setBusy(false)
      if (pendingRefresh.current) {
        pendingRefresh.current = false
        queueMicrotask(() => { void refresh() })
      }
    }
  }

  function refresh() {
    if (locked.current) { pendingRefresh.current = true; return Promise.resolve(false) }
    return run(async () => {
      // Never leave a previous account visible if session recovery fails.
      clearAccount()
      await loadAccount()
    }, true)
  }

  function signIn(email: string, password: string, register = false, username?: string) {
    return run(async () => {
      clearAccount()
      if (register) await accountRequest('/auth/register', 'POST', { email, password, username })
      await accountRequest('/auth/login', 'POST', { email, password })
      channel.current?.postMessage('changed')
      await loadAccount()
    })
  }

  function signOut() {
    return run(async () => {
      await accountRequest('/auth/logout', 'POST')
      clearAccount()
      channel.current?.postMessage('changed')
    })
  }

  function add(name: string, game: Game, price: number | null) {
    if (!user) { setError('Sign in from Profile to save items.'); return Promise.resolve(false) }
    return run(async () => {
      const saved = await accountRequest<SavedItem>('/watchlist', 'POST', {
        item_name: name, game, added_price_minor: price,
      }, user.id)
      setItems(current => [saved, ...current.filter(item => !same(item, name, game))])
      channel.current?.postMessage('changed')
    })
  }

  function remove(name: string, game: Game) {
    if (!user) { setError('Sign in from Profile to manage saved items.'); return Promise.resolve(false) }
    return run(async () => {
      await accountRequest('/watchlist', 'DELETE', { item_name: name, game }, user.id)
      setItems(current => current.filter(item => !same(item, name, game)))
      channel.current?.postMessage('changed')
    })
  }

  useEffect(() => {
    // Synchronize with the remote session after mounting (also safe in StrictMode).
    let active = true
    queueMicrotask(() => { if (active) void refresh() })
    const onFocus = () => { void refresh() }
    window.addEventListener('focus', onFocus)
    if (typeof BroadcastChannel !== 'undefined') {
      channel.current = new BroadcastChannel('vm-account-changed')
      channel.current.onmessage = onFocus
    }
    return () => {
      active = false
      window.removeEventListener('focus', onFocus)
      channel.current?.close()
      channel.current = null
    }
  }, [])

  return <AccountContext.Provider value={{ user, items, busy, error, refresh, signIn, signOut,
    has: (name, game) => items.some(item => same(item, name, game)), add, remove }}>
    {children}
  </AccountContext.Provider>
}
