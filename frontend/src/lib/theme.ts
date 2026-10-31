import { useEffect, useState } from 'react'

type Theme = 'light' | 'dark' | 'system'
const KEY = 'theme'

function read(): Theme {
  try {
    const v = localStorage.getItem(KEY)
    if (v === 'light' || v === 'dark') return v
  } catch {
    // private mode or blocked storage: fall back to system
  }
  return 'system'
}

function apply(theme: Theme): void {
  const root = document.documentElement
  if (theme === 'system') root.removeAttribute('data-theme')
  else root.setAttribute('data-theme', theme)
}

/** Light/dark toggle. Defaults to the OS setting; the choice is a per-viewer convenience. */
export function useTheme(): { theme: Theme; toggle: () => void } {
  const [theme, setTheme] = useState<Theme>(read)

  useEffect(() => {
    apply(theme)
  }, [theme])

  const toggle = (): void => {
    const effectiveDark =
      theme === 'dark' ||
      (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
    const next: Theme = effectiveDark ? 'light' : 'dark'
    setTheme(next)
    try {
      localStorage.setItem(KEY, next)
    } catch {
      // ignore: toggle still works for this session
    }
  }

  return { theme, toggle }
}
