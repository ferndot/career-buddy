import { Badge, Box, Button, Flex, Text } from '@chakra-ui/react'
import { useState } from 'react'
import { useDismiss, useDuplicates, useMerge } from './api'
import { FormDialog } from './FormDialog'

export function DuplicatesBanner() {
  const { data = [] } = useDuplicates()
  const merge = useMerge()
  const dismiss = useDismiss()
  const [open, setOpen] = useState(false)
  if (!data.length) return null
  const first = data[0]
  const n = data.length

  return (
    <>
      <Flex align="center" gap="3" mb="4" px="3" py="2" borderRadius="lg" borderWidth="1px" bg="app.warnPanel" borderColor="app.warnBorder">
        <Badge bg="app.warnBg" color="app.warnText" borderRadius="full" px="2" flexShrink={0}>
          {n} possible {n === 1 ? 'duplicate' : 'duplicates'}
        </Badge>
        <Text flex="1" minW="0" truncate fontSize="xs" color="app.text">
          "{first.a.title}" and "{first.b.title}" may be the same {first.kind.toLowerCase()}.
        </Text>
        <Button size="xs" variant="ghost" color="app.link" flexShrink={0} onClick={() => setOpen(true)}>
          Review
        </Button>
      </Flex>
      <FormDialog title="Possible duplicates" open={open} onClose={() => setOpen(false)}>
        {data.map((d) => (
          <Box key={`${d.a.id}-${d.b.id}`} mb="4">
            <Text fontSize="sm" mb="2">
              "{d.a.title}" and "{d.b.title}" ({d.kind})
            </Text>
            <Flex gap="2">
              <Button size="sm" bg="app.primary" color="app.onPrimary" loading={merge.isPending} onClick={() => merge.mutate({ alias_id: d.b.id, canonical_id: d.a.id })}>
                Merge
              </Button>
              <Button size="sm" variant="ghost" color="app.link" loading={dismiss.isPending} onClick={() => dismiss.mutate({ a_id: d.a.id, b_id: d.b.id })}>
                Not the same
              </Button>
            </Flex>
          </Box>
        ))}
      </FormDialog>
    </>
  )
}
