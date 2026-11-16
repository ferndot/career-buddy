import { Checkbox } from '@chakra-ui/react'
import type { ReactNode } from 'react'

type Props = { checked: boolean; onChange: (on: boolean) => void; label: string; children?: ReactNode; bold?: boolean }

/** A labelled Chakra checkbox. `label` is the accessible name; children replace the visible text. */
export function Check({ checked, onChange, label, children, bold }: Props) {
  return (
    <Checkbox.Root checked={checked} onCheckedChange={(e) => onChange(e.checked === true)} colorPalette="purple" alignItems="flex-start">
      <Checkbox.HiddenInput aria-label={label} />
      <Checkbox.Control mt="0.5" borderColor="app.borderStrong" />
      <Checkbox.Label fontSize={bold ? 'sm' : '13px'} fontWeight={bold ? 'semibold' : 'normal'} color={bold ? 'app.text' : 'app.text2'}>
        {children ?? label}
      </Checkbox.Label>
    </Checkbox.Root>
  )
}
