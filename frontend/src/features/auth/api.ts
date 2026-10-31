import { api, unwrap } from '@/lib/api/client'

export const login = async (email: string, password: string) =>
  unwrap(await api.POST('/api/v1/auth/login', { body: { email, password } }))

export const register = async (email: string, password: string, full_name: string) =>
  unwrap(await api.POST('/api/v1/auth/register', { body: { email, password, full_name } }))

export async function logout(): Promise<void> {
  await api.POST('/api/v1/auth/logout', {})
}
