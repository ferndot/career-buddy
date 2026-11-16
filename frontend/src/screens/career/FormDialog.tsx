import { Button, CloseButton, Dialog, Portal } from '@chakra-ui/react'
import type { ReactNode } from 'react'

type Props = {
  title: string
  open: boolean
  onClose: () => void
  children: ReactNode
  /** Omit for a read-only dialog (just a Close button). */
  submit?: { label: string; onSubmit: () => void; busy?: boolean; disabled?: boolean }
}

export function FormDialog({ title, open, onClose, children, submit }: Props) {
  return (
    <Dialog.Root open={open} onOpenChange={(d) => !d.open && onClose()} placement="center" lazyMount unmountOnExit>
      <Portal>
        <Dialog.Backdrop bg="app.scrim" />
        <Dialog.Positioner>
          <Dialog.Content bg="app.surface" color="app.text" borderRadius="lg" maxW="520px">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                submit?.onSubmit()
              }}
            >
              <Dialog.Header>
                <Dialog.Title>{title}</Dialog.Title>
              </Dialog.Header>
              <Dialog.Body>{children}</Dialog.Body>
              <Dialog.Footer>
                <Button type="button" variant="ghost" color="app.link" onClick={onClose}>
                  {submit ? 'Cancel' : 'Done'}
                </Button>
                {submit && (
                  <Button type="submit" bg="app.primary" color="app.onPrimary" loading={submit.busy} disabled={submit.disabled}>
                    {submit.label}
                  </Button>
                )}
              </Dialog.Footer>
              <Dialog.CloseTrigger asChild>
                <CloseButton size="sm" aria-label="Close" />
              </Dialog.CloseTrigger>
            </form>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  )
}
