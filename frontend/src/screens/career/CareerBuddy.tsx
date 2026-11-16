import { Box } from '@chakra-ui/react'
import { useTheme } from 'next-themes'
import { memo, useEffect, useMemo, useRef, useState } from 'react'
import ForceGraph2D, { type ForceGraphMethods } from 'react-force-graph-2d'
import type { Edge, Fact } from './api'
import { graphView, type GraphNode } from './graphLayout'
import { palette } from '../../theme/tokens'

type Pair = readonly [string, string]
/** Node colours per kind, as [light, dark] pairs from the theme palette. */
const KIND_COLOR: Record<string, { fill: Pair; ring: Pair }> = {
  Person: { fill: palette.primary, ring: palette.primary },
  Position: { fill: palette.nodeFill, ring: palette.nodeStroke },
  Education: { fill: palette.okBg, ring: palette.done },
  Organization: { fill: palette.surface, ring: palette.muted },
  Skill: { fill: palette.missBg, ring: palette.missText },
}
const TEXT: Pair = palette.text
const LINK: Pair = palette.muted
const RADIUS = 9
const FIT_MS = 400
const FIT_PADDING = 48
const CHARGE = -220
const LINK_DISTANCE = 70
/** Skills are the crowd (dozens of nodes): their labels wait for zoom or hover. */
const SKILL_LABEL_SCALE = 1.5

/** The stored career graph as a force-directed drawing: visible facts and links. Achievements show as a count on their position. */
export const CareerBuddy = memo(function CareerBuddy({ facts, edges }: { facts: Fact[]; edges: Edge[] }) {
  const { resolvedTheme } = useTheme()
  const mode = resolvedTheme === 'dark' ? 1 : 0
  const view = useMemo(() => graphView(facts, edges), [facts, edges])
  // Memoised on the view: the simulation reheats whenever this object changes identity, and typing elsewhere must not shake the graph.
  const data = useMemo(() => {
    return { nodes: view.nodes.map((n) => ({ ...n })), links: view.links.map((l) => ({ ...l })) }
  }, [view])

  const ref = useRef<HTMLDivElement>(null)
  const graph = useRef<ForceGraphMethods>(undefined)
  const fitted = useRef(false)
  const [hover, setHover] = useState<string | null>(null)
  const [size, setSize] = useState({ width: 0, height: 0 })
  const mounted = size.width > 0
  useEffect(() => {
    if (!mounted) return
    graph.current?.d3Force('charge')?.strength(CHARGE)
    graph.current?.d3Force('link')?.distance(LINK_DISTANCE)
    graph.current?.d3ReheatSimulation()
  }, [mounted])
  useEffect(() => {
    const el = ref.current
    if (!el) return
    // Measured, not the library default (the window size): this lives in one column of a grid.
    const observer = new ResizeObserver(([entry]) => {
      setSize({ width: entry.contentRect.width, height: entry.contentRect.height })
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  return (
    <Box ref={ref} as="section" aria-label={`Career graph: ${view.nodes.length} facts and ${view.links.length} links`}
      h={{ base: "70vh", md: "calc(100vh - 220px)" }} minH="480px" bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="lg" overflow="hidden">
      {size.width > 0 && (
        <ForceGraph2D
          ref={graph}
          width={size.width}
          height={size.height}
          graphData={data}
          nodeRelSize={RADIUS}
          nodeLabel={(n) => `${(n as GraphNode).title} (${(n as GraphNode).kind})`}
          linkColor={() => LINK[mode]}
          linkWidth={1.5}
          onNodeHover={(n) => setHover(n ? String((n as GraphNode).id) : null)}
          onEngineStop={() => {
            if (fitted.current) return
            fitted.current = true  // fit on the first settle only, not after every drag
            graph.current?.zoomToFit(FIT_MS, FIT_PADDING)
          }}
          nodeCanvasObject={(node, ctx, scale) => {
            const n = node as GraphNode & { x: number; y: number }
            const color = KIND_COLOR[n.kind] ?? KIND_COLOR.Organization
            ctx.beginPath()
            ctx.arc(n.x, n.y, RADIUS, 0, 2 * Math.PI)
            ctx.fillStyle = color.fill[mode]
            ctx.fill()
            ctx.lineWidth = 1.5 / scale
            ctx.strokeStyle = color.ring[mode]
            ctx.stroke()
            if (n.kind === 'Skill' && scale < SKILL_LABEL_SCALE && hover !== n.id) return
            const size = 11 / scale
            ctx.font = `${size}px Inter, sans-serif`
            ctx.textAlign = 'center'
            ctx.fillStyle = TEXT[mode]
            const label = n.achievements ? `${n.title} · ${n.achievements}` : n.title
            ctx.fillText(label.length > 26 ? `${label.slice(0, 25)}…` : label, n.x, n.y + RADIUS + size)
          }}
        />
      )}
    </Box>
  )
})
