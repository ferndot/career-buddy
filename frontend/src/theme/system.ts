import { createSystem, defaultConfig, defineConfig } from '@chakra-ui/react'
import { palette } from './tokens'

const colors = Object.fromEntries(
  Object.entries(palette).map(([key, [light, dark]]) => [
    key,
    { value: { _light: light, _dark: dark } },
  ]),
)

const config = defineConfig({
  globalCss: {
    body: { bg: 'app.bg', color: 'app.text' },
  },
  theme: {
    tokens: {
      fonts: {
        heading: { value: "'Inter', system-ui, sans-serif" },
        body: { value: "'Inter', system-ui, sans-serif" },
      },
    },
    semanticTokens: {
      colors: { app: colors },
    },
  },
})

export const system = createSystem(defaultConfig, config)
