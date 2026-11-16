import { Box, chakra } from '@chakra-ui/react'
import type { Career } from './model'

type Tone = { fill: string; stroke: string; text: string }
type Node = { label: string; sub: string; tone: Tone }

const W = 640
const H = 420
const cut = (s: string, n: number) => (s.length > n ? `${s.slice(0, n - 1)}…` : s)

const TONES = {
  pos: { fill: 'app.nodeFill', stroke: 'app.nodeStroke', text: 'app.nodeText' },
  edu: { fill: 'app.okBg', stroke: 'app.done', text: 'app.okText' },
  skill: { fill: 'app.missBg', stroke: 'app.missText', text: 'app.missText' },
} satisfies Record<string, Tone>

/** Person in the middle; positions, schools and one skills node on an ellipse around them. */
export function CareerGraph({ career }: { career: Career }) {
  const nodes: Node[] = [
    ...career.positions.map((p) => ({ label: cut(p.org || p.title, 12), sub: cut(p.title, 14), tone: TONES.pos })),
    ...career.education.map((e) => ({ label: cut(e.org || e.title, 12), sub: cut(e.title, 14), tone: TONES.edu })),
    ...(career.skills.length ? [{ label: 'Skills', sub: cut(career.skills.slice(0, 2).join(', '), 14), tone: TONES.skill }] : []),
  ]
  const r = nodes.length > 6 ? 30 : 40
  const cx = W / 2
  const cy = H / 2
  const at = (i: number) => {
    const a = (2 * Math.PI * i) / nodes.length - Math.PI * 0.75
    return { x: cx + 230 * Math.cos(a), y: cy + 140 * Math.sin(a) }
  }
  const summary = `Career graph: ${career.name} connected to ${career.positions.length} positions, ${career.education.length} education entries and ${career.skills.length} skills`

  return (
    <Box as="section" bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="lg" h="420px" overflow="hidden">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%" role="img" aria-label={summary}>
        {nodes.map((_, i) => (
          <chakra.line key={i} x1={cx} y1={cy} x2={at(i).x} y2={at(i).y} stroke="app.muted" strokeWidth="2" />
        ))}
        <chakra.circle cx={cx} cy={cy} r="48" fill="app.primary" />
        <chakra.text x={cx} y={cy + 5} textAnchor="middle" fontSize="14" fontWeight="600" fill="app.onPrimary">
          {cut(career.name, 14)}
        </chakra.text>
        {nodes.map((n, i) => {
          const { x, y } = at(i)
          return (
            <g key={i}>
              <chakra.circle cx={x} cy={y} r={r} fill={n.tone.fill} stroke={n.tone.stroke} strokeWidth="1.5" />
              <chakra.text x={x} y={y - 4} textAnchor="middle" fontSize="12" fill={n.tone.text}>
                {n.label}
              </chakra.text>
              <chakra.text x={x} y={y + 12} textAnchor="middle" fontSize="11" fill={n.tone.text}>
                {n.sub}
              </chakra.text>
            </g>
          )
        })}
      </svg>
    </Box>
  )
}
