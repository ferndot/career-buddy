import { Box, Text } from '@chakra-ui/react'
import { Fragment } from 'react'
import { LuCheck } from 'react-icons/lu'

export const STEP_LABELS = ['Job posting', 'Type and template', 'Details', 'Review and download']

export function StepIndicator({ current }: { current: number }) {
  return (
    <Box as="ol" aria-label="Wizard steps" display="flex" gap="2" flexWrap="wrap" listStyleType="none" p="0" mb="6" alignItems="center">
      {STEP_LABELS.map((label, i) => {
        const n = i + 1
        const done = n < current
        const cur = n === current
        return (
          <Fragment key={label}>
            <Box as="li" display="flex" alignItems="center" gap="2" fontSize="sm" fontWeight="medium" color={cur ? 'app.text' : 'app.muted'} aria-current={cur ? 'step' : undefined}>
              <Box
                w="26px"
                h="26px"
                borderRadius="full"
                display="inline-flex"
                alignItems="center"
                justifyContent="center"
                fontSize="13px"
                fontWeight="semibold"
                borderWidth="1px"
                borderColor={done ? 'app.done' : cur ? 'app.primary' : 'app.borderStrong'}
                bg={done ? 'app.done' : cur ? 'app.primary' : 'app.surface'}
                color={done || cur ? 'app.onPrimary' : 'app.text'}
                aria-hidden="true"
              >
                {done ? <LuCheck /> : n}
              </Box>
              <Text as="span">{label}</Text>
            </Box>
            {n < STEP_LABELS.length && <Box as="li" aria-hidden="true" w="8" h="1px" bg="app.borderStrong" />}
          </Fragment>
        )
      })}
    </Box>
  )
}
