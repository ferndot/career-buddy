import { Box, Flex, type FlexProps } from '@chakra-ui/react'

// Robot mark copied verbatim from the Sources mockup (viewBox 24x24).
export function CareerBuddyMark({ size = 28 }: { size?: number }) {
  return (
    <Box asChild flexShrink={0}>
      <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
        <line x1="12" y1="2.5" x2="12" y2="6" stroke="#6B46C1" strokeWidth="1.5" />
        <circle cx="12" cy="2.5" r="1.6" fill="#F6AD55" />
        <rect x="5" y="6" width="14" height="12" rx="4" fill="#7FD8BE" />
        <rect x="2.5" y="10" width="2" height="4" rx="1" fill="#6B46C1" />
        <rect x="19.5" y="10" width="2" height="4" rx="1" fill="#6B46C1" />
        <circle cx="9.2" cy="11.8" r="1.6" fill="#1A202C" />
        <circle cx="14.8" cy="11.8" r="1.6" fill="#1A202C" />
        <circle cx="7.5" cy="14.8" r="1" fill="#FBB6CE" />
        <circle cx="16.5" cy="14.8" r="1" fill="#FBB6CE" />
        <path d="M10 15.6q2 1.4 4 0" fill="none" stroke="#1A202C" strokeWidth="1.3" strokeLinecap="round" />
      </svg>
    </Box>
  )
}

export function CareerBuddyLogo(props: FlexProps) {
  return (
    <Flex align="center" gap="2" fontWeight="bold" fontSize="lg" color="app.text" {...props}>
      <CareerBuddyMark />
      Career Buddy
    </Flex>
  )
}
