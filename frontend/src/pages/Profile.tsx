import { PagePlaceholder } from '../components/PagePlaceholder'

export function Profile() {
  return (
    <PagePlaceholder
      summary="The signed-in user's account: name, Steam ID, and watchlist settings."
      willShow={['Username and Steam ID', 'Watchlist size and alert settings', 'Sign out']}
      needs={['Login and user accounts (Jerome)']}
    />
  )
}
