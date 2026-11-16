import { Button, Dialog, Portal } from '@chakra-ui/react'
import type { SavedDocument } from './api'

type Props = { doc: SavedDocument | null; onCancel: () => void; onConfirm: (doc: SavedDocument) => void }

export function DeleteDialog({ doc, onCancel, onConfirm }: Props) {
  return (
    <Dialog.Root role="alertdialog" open={doc !== null} onOpenChange={(e) => !e.open && onCancel()}>
      <Portal>
        <Dialog.Backdrop bg="app.scrim" />
        <Dialog.Positioner>
          <Dialog.Content bg="app.surface" color="app.text" borderColor="app.border" borderWidth="1px">
            <Dialog.Header>
              <Dialog.Title>Delete this document?</Dialog.Title>
            </Dialog.Header>
            <Dialog.Body color="app.text3">
              {doc?.label} will be removed from your list. You can generate it again any time.
            </Dialog.Body>
            <Dialog.Footer>
              <Button variant="outline" borderColor="app.borderStrong" color="app.text" onClick={onCancel}>
                Cancel
              </Button>
              <Button bg="app.missBg" color="app.missText" onClick={() => doc && onConfirm(doc)}>
                Delete
              </Button>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  )
}
