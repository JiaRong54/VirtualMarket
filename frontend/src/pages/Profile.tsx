import { PagePlaceholder } from '../components/PagePlaceholder'

export function Profile() {
  return (
    <PagePlaceholder
      summary="The signed-in user's account: name and Steam ID."
      willShow={['Username and Steam ID', 'Sign out']}
      needs={['Login and user accounts (Jerome)']}
    />
  )
}
