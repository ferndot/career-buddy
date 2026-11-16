import { Text } from '@chakra-ui/react'

export const STEP_LABELS = ['Job posting', 'Documents', 'Facts', 'Template', 'Download']

export function StepIndicator({ current }: { current: number }) {
  return (
    <Text aria-label="Progress" color="app.muted" fontSize="sm" mb="4">
      Step {current} of {STEP_LABELS.length} · {STEP_LABELS[current - 1]}
    </Text>
  )
}
