import { PagePlaceholder } from '../components/PagePlaceholder'

export function Compare() {
  return (
    <PagePlaceholder
      summary="Price history for variants of the same skin side by side, like an AK-47 Redline in Field-Tested next to Minimal Wear."
      willShow={[
        'Two or more variants on one chart',
        'Current price and listing count for each',
        'Price gap between variants over time',
      ]}
      needs={['Price history endpoint in the API (Jerome)', 'A few weeks of stored snapshots']}
    />
  )
}
