import { Box, Button, Text } from '@chakra-ui/react'
import { useState } from 'react'
import { LuDownload } from 'react-icons/lu'
import { RobotMascot } from '../../brand'
import { DOWNLOAD_FORMATS, downloadSaved, type SavedDocument } from '../documents/api'
import { kindLabel, type DocKind } from './state'

type Props = {
  kind: DocKind
  saved: boolean // the saved copy matches what is on screen
  save: () => Promise<SavedDocument>
}

/** Saving creates the saved document once; each format button then downloads it, converted on the fly. */
export function DownloadStep({ kind, saved, save }: Props) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const run = async (format?: string) => {
    setBusy(true)
    setError('')
    try {
      const doc = await save()
      if (format) await downloadSaved(doc, format)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }
  return (
    <Box bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="lg" p="5" display="flex" flexDirection="column" gap="4" alignItems="flex-start" minW="0">
      {saved && (
        <Box display="flex" alignItems="center" gap="3" role="status">
          <RobotMascot mood="celebrate" size={64} />
          <Text fontWeight="semibold" color="app.okText" bg="app.okBg" borderRadius="md" px="3" py="1">{kindLabel(kind)} saved to your documents</Text>
        </Box>
      )}
      <Text fontWeight="semibold">Download the {kindLabel(kind).toLowerCase()}</Text>
      <Box display="flex" gap="2" flexWrap="wrap" role="group" aria-label={`Download format for ${kindLabel(kind)}`}>
        {DOWNLOAD_FORMATS.map((f) => (
          <Button key={f.format} bg="app.primary" color="app.onPrimary" disabled={busy} onClick={() => void run(f.format)}>
            <LuDownload /> {f.label}
          </Button>
        ))}
      </Box>
      {!saved && (
        <Button variant="ghost" color="app.link" pl="0" disabled={busy} onClick={() => void run()}>Save without downloading</Button>
      )}
      {error && <Text role="alert" fontSize="13px" color="app.missText" bg="app.missBg" borderRadius="md" px="3" py="2">{error}</Text>}
    </Box>
  )
}
