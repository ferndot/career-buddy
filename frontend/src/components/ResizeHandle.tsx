import { Box } from '@chakra-ui/react'
import { MIN_WIDTH, useResizableWidth } from './useResizableWidth'

/** The drag handle on the left edge of a right-hand sidebar; `size` is what useResizableWidth returned. */
export function ResizeHandle({ label, size }: { label: string; size: ReturnType<typeof useResizableWidth> }) {
  const { width, handle, max } = size
  return (
    <Box
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-valuenow={width}
      aria-valuemin={MIN_WIDTH}
      aria-valuemax={max}
      tabIndex={0}
      {...handle}
      display="block"
      position="absolute"
      left="-3px"
      top="0"
      bottom="0"
      w="6px"
      cursor="col-resize"
      touchAction="none"
      borderRadius="full"
      _hover={{ bg: 'app.borderStrong' }}
      _focusVisible={{ bg: 'app.primary', outline: 'none' }}
    />
  )
}
