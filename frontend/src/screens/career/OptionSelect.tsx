import { NativeSelect } from '@chakra-ui/react'

/** A native select over `options` with a leading empty choice labelled `empty`. */
export function OptionSelect({ value, onChange, options, empty }: { value: string; onChange: (v: string) => void; options: readonly string[]; empty: string }) {
  return (
    <NativeSelect.Root>
      <NativeSelect.Field value={value} onChange={(e) => onChange(e.target.value)} bg="app.surface" borderColor="app.borderStrong">
        <option value="">{empty}</option>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </NativeSelect.Field>
    </NativeSelect.Root>
  )
}
