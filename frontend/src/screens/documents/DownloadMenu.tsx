import { Button, Menu, Portal } from '@chakra-ui/react'
import { DOWNLOAD_FORMATS, downloadSaved, type SavedDocument } from './api'

/** The Download button of a saved document: Word, PDF or Text. `onResult` gets the error message, or '' once a file is saved. */
export function DownloadMenu({ doc, onResult }: { doc: SavedDocument; onResult: (error: string) => void }) {
  const get = (format: string) =>
    downloadSaved(doc, format).then(
      () => onResult(''),
      (e: Error) => onResult(`${doc.label}: ${e.message}`),
    )
  return (
    <Menu.Root>
      <Menu.Trigger asChild>
        <Button size="sm" variant="outline" borderColor="app.borderStrong" color="app.text" aria-label={`Download ${doc.label}`}>
          Download
        </Button>
      </Menu.Trigger>
      <Portal>
        <Menu.Positioner>
          <Menu.Content bg="app.surface" color="app.text" borderColor="app.border">
            {DOWNLOAD_FORMATS.map((f) => (
              <Menu.Item key={f.format} value={f.format} onClick={() => void get(f.format)}>{f.label}</Menu.Item>
            ))}
          </Menu.Content>
        </Menu.Positioner>
      </Portal>
    </Menu.Root>
  )
}
