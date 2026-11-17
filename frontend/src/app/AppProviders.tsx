import { QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { queryClient } from '../api'
import { ActivityProvider, Toaster } from '../components'
import { ThemeProvider } from '../theme'

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <ActivityProvider>{children}</ActivityProvider>
        <Toaster />
      </QueryClientProvider>
    </ThemeProvider>
  )
}
