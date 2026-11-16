import { Box } from '@chakra-ui/react'
import { Background, Controls, ReactFlow, type Edge as FlowEdge, type Node } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useMemo } from 'react'
import { useTheme } from 'next-themes'
import type { Edge, Fact } from './api'
import { layoutGraph, NODE_H, NODE_W } from './graphLayout'
import { palette } from '../../theme/tokens'

type Pair = readonly [string, string]
const TONES: Record<string, { fill: Pair; stroke: Pair; text: Pair }> = {
  Person: { fill: palette.primary, stroke: palette.primary, text: palette.surface },
  Position: { fill: palette.nodeFill, stroke: palette.nodeStroke, text: palette.nodeText },
  Education: { fill: palette.okBg, stroke: palette.done, text: palette.okText },
  Organization: { fill: palette.surface, stroke: palette.muted, text: palette.nodeText },
  Skill: { fill: palette.missBg, stroke: palette.missText, text: palette.missText },
}
const EDGE_COLOR: Pair = palette.muted

/** The stored career graph: visible facts and links, laid out left to right. Achievements show as a count on their position. */
export function CareerGraph({ facts, edges }: { facts: Fact[]; edges: Edge[] }) {
  const { resolvedTheme } = useTheme()
  const mode = resolvedTheme === 'dark' ? 1 : 0
  const layout = useMemo(() => layoutGraph(facts, edges), [facts, edges])

  const nodes: Node[] = layout.nodes.map((n) => {
    const tone = TONES[n.kind]
    const badge = layout.badges[n.id]
    return {
      id: n.id,
      position: { x: n.x, y: n.y },
      data: {
        label: (
          <div style={{ lineHeight: 1.25 }}>
            <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={n.title}>
              {n.title}
            </div>
            <div style={{ fontSize: 11, opacity: 0.85 }}>
              {n.kind}
              {badge ? ` · ${badge} ${badge === 1 ? 'achievement' : 'achievements'}` : ''}
            </div>
          </div>
        ),
      },
      style: {
        width: NODE_W,
        height: NODE_H,
        padding: '6px 10px',
        borderRadius: 8,
        border: `1.5px solid ${tone.stroke[mode]}`,
        background: tone.fill[mode],
        color: tone.text[mode],
        fontSize: 12,
      },
      selectable: false,
    }
  })
  const flowEdges: FlowEdge[] = layout.edges.map((e) => ({
    id: `${e.kind}:${e.source}:${e.target}`,
    source: e.source,
    target: e.target,
    style: { stroke: EDGE_COLOR[mode], strokeWidth: 1.5 },
    selectable: false,
  }))

  const summary = `Career graph: ${layout.nodes.length} facts and ${layout.edges.length} links`
  return (
    <Box as="section" aria-label={summary} h="480px" bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="lg" overflow="hidden">
      <ReactFlow
        nodes={nodes}
        edges={flowEdges}
        fitView
        fitViewOptions={{ padding: 0.12 }}
        minZoom={0.2}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls showInteractive={false} />
      </ReactFlow>
    </Box>
  )
}
