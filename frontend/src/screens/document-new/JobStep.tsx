import { Box, Button, Field, Input, Text, Textarea } from '@chakra-ui/react'
import { useMutation } from '@tanstack/react-query'
import { LuDownload } from 'react-icons/lu'
import { fetchJobText } from '../documents/api'
import type { Wizard } from './state'

type Props = { w: Wizard; set: (patch: Partial<Wizard>) => void }

export function JobStep({ w, set }: Props) {
  const fetchJob = useMutation({
    mutationFn: () => fetchJobText(w.jobUrl.trim()),
    onSuccess: (r) => set({ jobText: r.text, prefilled: false }),
  })
  return (
    <Box bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="lg" p="5" display="flex" flexDirection="column" gap="5">
      <Field.Root>
        <Field.Label color="app.text2">Link to the job posting</Field.Label>
        <Box display="flex" gap="2" w="full">
          <Input type="url" placeholder="https://example.com/jobs/123" value={w.jobUrl} onChange={(e) => set({ jobUrl: e.target.value })} bg="app.surface" borderColor="app.borderStrong" color="app.text" />
          <Button variant="outline" borderColor="app.borderStrong" color="app.text" loading={fetchJob.isPending} disabled={!w.jobUrl.trim()} onClick={() => fetchJob.mutate()}>
            <LuDownload /> Fetch
          </Button>
        </Box>
        {fetchJob.isError && (
          <Text role="alert" color="app.missText" bg="app.missBg" fontSize="sm" px="3" py="1" borderRadius="md" mt="2">
            Could not fetch that link. Paste the posting text below instead.
          </Text>
        )}
      </Field.Root>
      <Field.Root>
        <Field.Label color="app.text2">Or paste the job posting</Field.Label>
        <Textarea rows={12} placeholder="Paste the full text of the posting. Leave empty for a general document." value={w.jobText} onChange={(e) => set({ jobText: e.target.value, prefilled: false })} bg="app.surface" borderColor="app.borderStrong" color="app.text" />
        <Field.HelperText color="app.muted">Optional. Without a posting you get a general document with all your facts.</Field.HelperText>
      </Field.Root>
    </Box>
  )
}
