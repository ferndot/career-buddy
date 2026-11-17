import { Text } from '@chakra-ui/react'

export const STEP_LABELS = ['Job posting', 'Documents', 'Missing requirements', 'Template and preview', 'Download']

export function StepIndicator({ current }: { current: number }) {
  return (
    <Text aria-label="Progress" color="app.muted" fontSize="sm">
      Step {current} of {STEP_LABELS.length} · {STEP_LABELS[current - 1]}
    </Text>
  )
}
