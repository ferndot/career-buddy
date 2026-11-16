const NAMES: Record<string, string> = {
  'resume-text': 'Pasted text',
}

export const displayName = (source: string) => NAMES[source] ?? source

export const factsLabel = (n: number) => `${n} ${n === 1 ? 'fact' : 'facts'} found`
