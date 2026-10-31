import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { toast } from 'sonner'
import * as authApi from './api'
import { useAuth } from './authStore'
import { errorMessage, refreshSession } from '@/lib/api/client'

/** On first load, try to restore a session from the refresh cookie, then mark auth ready. */
export function useBootstrapAuth(): boolean {
  const ready = useAuth((s) => s.ready)
  const setReady = useAuth((s) => s.setReady)

  useEffect(() => {
    if (ready) return
    void refreshSession().finally(setReady)
  }, [ready, setReady])

  return ready
}

export function useLogin() {
  const setSession = useAuth((s) => s.setSession)
  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      authApi.login(email, password),
    onSuccess: (token) => setSession(token.access_token, token.user),
    onError: (e) => toast.error(errorMessage(e, 'Could not sign in')),
  })
}

export function useRegister() {
  const login = useLogin()
  return useMutation({
    mutationFn: ({
      email,
      password,
      full_name,
    }: {
      email: string
      password: string
      full_name: string
    }) => authApi.register(email, password, full_name),
    onSuccess: (_user, vars) => login.mutate({ email: vars.email, password: vars.password }),
    onError: (e) => toast.error(errorMessage(e, 'Could not create the account')),
  })
}

export function useLogout() {
  const clear = useAuth((s) => s.clear)
  const qc = useQueryClient()
  return useMutation({
    mutationFn: authApi.logout,
    onSettled: () => {
      clear()
      qc.clear()
      // A full load drops router state, so the next person doesn't land on this user's page.
      window.location.assign('/login')
    },
  })
}
