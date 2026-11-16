import { Button, Flex, Text } from '@chakra-ui/react'
import { useTheme } from 'next-themes'
import { useEffect, useState } from 'react'

const CHOICES = [['light', 'Light'], ['dark', 'Dark'], ['system', 'System']] as const

export function AppearanceSettings() {
  const { theme, setTheme } = useTheme()
  // theme is undefined on first render (SSR-safe in next-themes); wait for mount.
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  return (
    <>
      <Text as="h2" fontWeight="semibold" color="app.text" mb="3">Color mode</Text>
      <Flex role="group" aria-label="Color mode" gap="2">
        {CHOICES.map(([value, label]) => {
          const on = mounted && theme === value
          return (
            <Button
              key={value}
              aria-pressed={on}
              variant={on ? 'solid' : 'outline'}
              bg={on ? 'app.primary' : undefined}
              color={on ? 'app.onPrimary' : 'app.text'}
              onClick={() => setTheme(value)}
            >
              {label}
            </Button>
          )
        })}
      </Flex>
    </>
  )
}
