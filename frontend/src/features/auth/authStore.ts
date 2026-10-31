import { create } from 'zustand'
import type { Me } from '@/lib/api/types'

// Access token lives in memory only (never localStorage). It is refreshed from the
// HttpOnly cookie on page load and on 401.
interface AuthState {
  accessToken: string | null
  user: Me | null
  ready: boolean // the initial refresh attempt has finished
  setSession: (accessToken: string, user: Me) => void
  setUser: (user: Me) => void
  clear: () => void
  setReady: () => void
}

/** The signed-in user. Only for pages behind RequireAuth, where a user always exists. */
export function useMe(): Me {
  const user = useAuth((s) => s.user)
  if (!user) throw new Error('useMe() used outside RequireAuth')
  return user
}

export const useAuth = create<AuthState>((set) => ({
  accessToken: null,
  user: null,
  ready: false,
  setSession: (accessToken, user) => set({ accessToken, user }),
  setUser: (user) => set({ user }),
  clear: () => set({ accessToken: null, user: null }),
  setReady: () => set({ ready: true }),
}))
