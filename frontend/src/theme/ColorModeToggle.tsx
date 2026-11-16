import { IconButton } from '@chakra-ui/react'
import { useTheme } from 'next-themes'
import { useEffect, useState } from 'react'
import { LuMoon, LuSun } from 'react-icons/lu'

export function ColorModeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  // resolvedTheme is undefined on first render (SSR-safe in next-themes); wait for mount.
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  const dark = mounted && resolvedTheme === 'dark'

  return (
    <IconButton
      aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
      variant="ghost"
      size="sm"
      color="app.text3"
      _hover={{ bg: 'app.hover', color: 'app.text' }}
      onClick={() => setTheme(dark ? 'light' : 'dark')}
    >
      {dark ? <LuSun /> : <LuMoon />}
    </IconButton>
  )
}
