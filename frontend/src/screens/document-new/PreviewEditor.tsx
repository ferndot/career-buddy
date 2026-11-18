import { Box, Button, Text } from '@chakra-ui/react'
import { useState, type ClipboardEvent } from 'react'
import type { Flag, TemplateLayout } from '../documents/api'
import type { SlotDoc } from './layout'
import { readEdits, sheetCss, sheetDefaults, sheetHtml } from './sheet'

type Props = {
  doc: SlotDoc // the layout with slot ids
  layout: TemplateLayout // the template's page arrangement and CSS
  title: string // names the sheet: what the document is
  defaults: Record<string, string> // each slot's text without the user's edits: the writer's
  flags: Record<string, Flag> // slots the writer could not do properly
  overrides: Record<string, string>
  onChange: (overrides: Record<string, string>) => void
}

/**
 * The document as one editable sheet in the template's own CSS: the person edits the whole text in one place, changing, adding,
 * removing and moving lines. What that saves as overrides is described in `sheet.ts`. The name, contact lines and section titles are
 * fixed. The sheet is built once for a draft: typing must not rebuild it (the caret would jump), so a new draft or Reset rebuilds it.
 */
export function PreviewEditor({ doc, layout, title, defaults, flags, overrides, onChange }: Props) {
  const [version, setVersion] = useState(0)
  const slots = Object.keys(sheetDefaults(doc, defaults))
  const edited = slots.some((s) => s in overrides)
  const reset = () => {
    onChange(Object.fromEntries(Object.entries(overrides).filter(([k]) => !slots.includes(k))))
    setVersion((v) => v + 1)
  }
  const notes = Object.entries(flags).filter(([slot]) => slot in sheetDefaults(doc, defaults) && !(slot in overrides)) // once the person wrote it there is nothing to flag
  return (
    <Box display="flex" flexDirection="column" gap="2">
      <Sheet key={`${version}:${JSON.stringify(doc)}`} {...{ doc, layout, title, defaults, overrides, onChange }} />
      {edited && (
        <Box display="flex" alignItems="center" gap="2" fontSize="xs" color="#5b6472">
          Edited
          <Button size="2xs" variant="ghost" color="#1d4ed8" onClick={reset}>Reset to generated</Button>
        </Box>
      )}
      {notes.map(([slot, flag]) => <FlagNote key={slot} text={defaults[slot] ?? ''} flag={flag} />)}
    </Box>
  )
}

/** Why a flagged slot looks as it does. */
function FlagNote({ text, flag }: { text: string; flag: Flag }) {
  const why = flag.reasons.join('; ')
  return (
    <Text role="status" fontSize="xs" color="#9a5b00">
      {flag.code === 'not_rewritten' ? `Not rewritten (${text}): the writer's wording did not match your facts, so this is your own text. ${why}` : `Left empty: the writer's text did not match your facts. ${why}. Write it yourself or generate again.`}
    </Text>
  )
}

/** Plain text only: pasted markup would bring its own styles into the sheet. */
const paste = (e: ClipboardEvent) => {
  e.preventDefault()
  document.execCommand('insertText', false, e.clipboardData.getData('text/plain'))
}

function Sheet({ doc, layout, title, defaults, overrides, onChange }: Omit<Props, 'flags'>) {
  const [html] = useState(() => sheetHtml(doc, layout, defaults, overrides)) // set once: React leaves the DOM alone while the string is the same
  return (
    <Box borderWidth="1px" borderColor="#d5d9e0" borderRadius="md" boxShadow="sm" overflow="hidden" maxH="560px" overflowY="auto">
      <style>{sheetCss(layout)}</style>
      <div
        className="sheet"
        role="textbox"
        aria-multiline="true"
        aria-label={`Edit the ${title}`}
        contentEditable
        suppressContentEditableWarning
        onPaste={paste}
        onDrop={(e) => e.preventDefault()} // a dragged line would bring its slot id along: move a line by cutting and pasting it
        onInput={(e) => onChange(readEdits(e.currentTarget, doc, defaults, overrides))}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </Box>
  )
}
