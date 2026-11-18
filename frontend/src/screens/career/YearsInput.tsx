import { Input } from '@chakra-ui/react'

/** A skill's years: whole numbers only. Anything else typed is ignored. */
export function YearsInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <Input type="number" min={0} step={1} inputMode="numeric" bg="app.surface" borderColor="app.borderStrong" placeholder="5" value={value}
      onChange={(e) => /^\d*$/.test(e.target.value) && onChange(e.target.value)} />
  )
}
