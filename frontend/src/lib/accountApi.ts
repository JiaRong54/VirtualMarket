export interface User {
  id: number
  email: string
  created_at: number
}

export class AccountApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** Same-origin cookies identify the account; credentials never enter localStorage. */
export async function accountRequest<T>(path: string, method = 'GET', body?: unknown, userId?: number): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    credentials: 'same-origin',
    cache: 'no-store',
    headers: {
      'Content-Type': 'application/json',
      'X-VirtualMarket': '1',
      ...(userId === undefined ? {} : { 'X-VirtualMarket-User': String(userId) }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new AccountApiError(response.status,
      typeof data?.detail === 'string' ? data.detail : `Request failed (${response.status}). Please try again.`)
  }
  return response.json() as Promise<T>
}
