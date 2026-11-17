import { useState } from 'react'
import type { FormEvent } from 'react'
import { useWatchlist } from '../lib/watchlist'
import { Watchlist } from './Watchlist'

export function Profile() {
  const { user, busy, signIn, signOut } = useWatchlist()
  const [register, setRegister] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [validation, setValidation] = useState('')

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setValidation('')
    if (register && password !== confirm) { setValidation('Passwords do not match.'); return }
    if (await signIn(email, password, register)) { setPassword(''); setConfirm('') }
  }

  if (user) return <>
    <section className="card account-panel">
      <div><h2>{user.email}</h2><p>Your watchlist is saved to this account and restored whenever you sign in.</p></div>
      <button className="watch-btn" disabled={busy} onClick={() => void signOut()}>Sign out</button>
    </section>
    <Watchlist />
  </>

  return <section className="card account-panel">
    <h2>{register ? 'Create an account' : 'Sign in'}</h2>
    <p>Sign in to save your watchlist and access it on another browser or device.</p>
    <form className="account-form" onSubmit={onSubmit}>
      <label>Email<input type="email" autoComplete="email" maxLength={254} required value={email} onChange={event => setEmail(event.target.value)} /></label>
      <label>Password<input type="password" autoComplete={register ? 'new-password' : 'current-password'} minLength={12} maxLength={128} required value={password} onChange={event => setPassword(event.target.value)} /></label>
      {register && <><span className="muted">Use 12–128 characters.</span><label>Confirm password<input type="password" autoComplete="new-password" required value={confirm} onChange={event => setConfirm(event.target.value)} /></label></>}
      {validation && <p role="alert">{validation}</p>}
      <button className="watch-btn on" disabled={busy} type="submit">{register ? 'Create account and sign in' : 'Sign in'}</button>
      <button className="link-btn" disabled={busy} type="button" onClick={() => { setRegister(!register); setValidation(''); setPassword(''); setConfirm('') }}>
        {register ? 'Already registered? Sign in' : 'New here? Create an account'}
      </button>
    </form>
  </section>
}
