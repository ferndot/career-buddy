import { ChakraProvider } from '@chakra-ui/react'
import { ThemeProvider as ColorModeProvider } from 'next-themes'
import type { ReactNode } from 'react'
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/inter/700.css'
import { system } from './system'

// Chakra's `_dark` condition matches `.dark`, which next-themes toggles on <html>.
export function ThemeProvider({ children }: { children: ReactNode }) {
  return (
    <ColorModeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <ChakraProvider value={system}>{children}</ChakraProvider>
    </ColorModeProvider>
  )
}
