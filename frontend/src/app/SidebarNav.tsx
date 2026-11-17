import { Flex, Icon, Link } from '@chakra-ui/react'
import { NavLink } from 'react-router-dom'
import { LogsButton } from '../components'
import { navItems } from './nav'

// Column on desktop; wraps into a row in the top bar on narrow screens.
export function SidebarNav() {
  return (
    <Flex as="nav" aria-label="Main" flex={{ md: '1' }} direction={{ base: 'row', md: 'column' }} wrap="wrap" gap="1">
      {navItems.map(({ to, label, icon, pinned }) => (
        <Flex key={to} align="center" gap="1" mt={pinned ? { md: 'auto' } : undefined} ml={pinned ? { base: 'auto', md: 0 } : undefined}>
          <Link
            asChild
            display="flex"
            flex="1"
            alignItems="center"
            gap="2.5"
            px="3"
            py="2.5"
            borderRadius="md"
            fontSize="sm"
            fontWeight="medium"
            color="app.text3"
            textDecoration="none"
            _hover={{ bg: 'app.hover', color: 'app.text', textDecoration: 'none' }}
            _currentPage={{ bg: 'app.activeBg', color: 'app.activeText' }}
            _focusVisible={{ outlineColor: 'app.primary' }}
          >
            <NavLink to={to}>
              <Icon as={icon} boxSize="18px" />
              {label}
            </NavLink>
          </Link>
          {pinned && <LogsButton />}
        </Flex>
      ))}
    </Flex>
  )
}
