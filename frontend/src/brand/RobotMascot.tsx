import { Box } from '@chakra-ui/react'
import { useSyncExternalStore } from 'react'

export type Mood = 'happy' | 'thinking' | 'celebrate'

// Same robot as CareerBuddyMark, drawn larger with moods and a few gentle animations.
const CSS = `
.cb-anim .cb-body { animation: cb-bob 3s ease-in-out infinite; }
.cb-anim.cb-celebrate .cb-body { animation: cb-jump 0.9s ease-in-out infinite; }
.cb-anim .cb-eye, .cb-anim .cb-ant, .cb-anim .cb-arm { transform-box: fill-box; }
.cb-anim .cb-eye { transform-origin: center; animation: cb-blink 4s infinite; }
.cb-anim .cb-ant { transform-origin: 50% 100%; animation: cb-wiggle 2.8s ease-in-out infinite; }
.cb-anim .cb-arm { transform-origin: 50% 0; animation: cb-wave 1.6s ease-in-out infinite; }
.cb-anim .cb-arm.cb-left { animation-direction: reverse; }
.cb-anim .cb-glow { animation: cb-pulse 1s ease-in-out infinite; }
@keyframes cb-bob { 50% { transform: translateY(-0.8px); } }
@keyframes cb-jump { 40% { transform: translateY(-2px); } }
@keyframes cb-blink { 0%, 92%, 100% { transform: scaleY(1); } 96% { transform: scaleY(0.1); } }
@keyframes cb-wiggle { 0%, 70%, 100% { transform: rotate(0); } 78% { transform: rotate(-14deg); } 86% { transform: rotate(12deg); } 94% { transform: rotate(-6deg); } }
@keyframes cb-wave { 0%, 100% { transform: rotate(0); } 50% { transform: rotate(-35deg); } }
@keyframes cb-pulse { 50% { opacity: 0.35; } }
`

const QUERY = '(prefers-reduced-motion: reduce)'
const subscribe = (cb: () => void) => {
  const m = window.matchMedia(QUERY)
  m.addEventListener('change', cb)
  return () => m.removeEventListener('change', cb)
}
const prefersReducedMotion = () => window.matchMedia(QUERY).matches

const MOUTH: Record<Mood, string> = {
  happy: 'M10 15.6q2 1.4 4 0',
  thinking: 'M10.6 16.2h2.8',
  celebrate: 'M10.2 15.3h3.6q0 2-1.8 2t-1.8-2z',
}

export function RobotMascot({ mood = 'happy', size = 96 }: { mood?: Mood; size?: number }) {
  const still = useSyncExternalStore(subscribe, prefersReducedMotion)
  const waves = mood !== 'thinking'
  return (
    <Box asChild flexShrink={0} overflow="visible">
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        aria-hidden="true"
        data-mascot={mood}
        className={still ? undefined : `cb-anim cb-${mood}`}
      >
        <style>{CSS}</style>
        <g className="cb-body">
          <g className="cb-ant">
            <line x1="12" y1="2.5" x2="12" y2="6" stroke="#6B46C1" strokeWidth="1.5" />
            <circle className={mood === 'thinking' ? 'cb-glow' : undefined} cx="12" cy="2.5" r="1.6" fill="#F6AD55" />
          </g>
          <rect x="5" y="6" width="14" height="12" rx="4" fill="#7FD8BE" />
          <rect className="cb-arm cb-left" x="2.5" y="10" width="2" height="4" rx="1" fill="#6B46C1" style={mood === 'celebrate' ? undefined : { animation: 'none' }} />
          <rect className="cb-arm" x="19.5" y="10" width="2" height="4" rx="1" fill="#6B46C1" style={waves ? undefined : { animation: 'none' }} />
          <circle className="cb-eye" cx="9.2" cy="11.8" r="1.6" fill="#1A202C" />
          <circle className="cb-eye" cx="14.8" cy="11.8" r="1.6" fill="#1A202C" />
          <circle cx="7.5" cy="14.8" r="1" fill="#FBB6CE" />
          <circle cx="16.5" cy="14.8" r="1" fill="#FBB6CE" />
          <path d={MOUTH[mood]} fill={mood === 'celebrate' ? '#1A202C' : 'none'} stroke="#1A202C" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
        </g>
      </svg>
    </Box>
  )
}
