import { Box, Text } from '@chakra-ui/react'
import type { Template } from '../documents/api'
import { Page, type Part } from './Page'

const GREY = '#d5d9e0'
const WIDTHS = ['100%', '92%', '68%']

/** One grey bar standing in for a line of text. */
const Bar = ({ w, dark, dot }: { w: string; dark?: boolean; dot?: boolean }) => (
  <Box display="flex" alignItems="center" gap="2">
    {dot && <Box w="4px" h="4px" borderRadius="full" bg={GREY} flexShrink={0} />}
    <Box data-testid="bar" h="7px" w={w} borderRadius="full" bg={dark ? '#aab0bb' : GREY} />
  </Box>
)

const bars = (n: number, dot = false) => Array.from({ length: n }, (_, i) => <Bar key={i} w={WIDTHS[i % 3]} dot={dot} />)

/** What a section looks like as bars: where its headings, paragraphs and bullets fall. */
function body(title: string): Part['node'] {
  if (title === 'Experience') {
    return [0, 1].map((i) => (
      <Box key={i} display="flex" flexDirection="column" gap="1" mb="1">
        <Bar w="62%" dark />
        {bars(2, true)}
      </Box>
    ))
  }
  if (title === 'Education') return <Bar w="80%" dot />
  return <Box display="flex" flexDirection="column" gap="1">{bars(title === 'Skills' ? 2 : 3)}</Box>
}

/** The template step's preview: the layout of the chosen template with bars in place of text. No fact's text is shown. */
export function Wireframe({ template }: { template: Template }) {
  const band = template.layout.header === 'band'
  const parts: Part[] = template.kind === 'letter'
    ? [{ title: '', node: [0, 1, 2].map((i) => <Box key={i} display="flex" flexDirection="column" gap="1" mb="3">{bars(i === 1 ? 4 : 3)}</Box>) }]
    : template.sections.map((title) => ({ title, node: body(title) }))
  const head = (
    <>
      <Box data-testid="bar" h="12px" w="45%" borderRadius="full" bg={band ? '#dbe6f4' : '#8d94a1'} />
      <Box data-testid="bar" h="7px" w="30%" borderRadius="full" bg={band ? '#9db4d3' : GREY} />
    </>
  )
  return (
    <Box display="flex" flexDirection="column" gap="2" bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="lg" p="5">
      <Text fontWeight="semibold">Layout</Text>
      <Text fontSize="xs" color="app.muted">The layout of the {template.label.toLowerCase()}. The text is written on the next step.</Text>
      <Page testId="wireframe" label={`Layout of the ${template.label}`} layout={template.layout} head={head} parts={parts} />
    </Box>
  )
}
