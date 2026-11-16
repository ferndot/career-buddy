import { Box, Flex } from '@chakra-ui/react'
import { Outlet } from 'react-router-dom'
import { CareerBuddyLogo } from '../brand'
import { SidebarNav } from './SidebarNav'

export function AppShell() {
  return (
    <Flex direction={{ base: 'column', md: 'row' }} minH="100vh" bg="app.bg" color="app.text">
      <Flex
        as="aside"
        direction="column"
        flex={{ md: '0 0 232px' }}
        w={{ base: 'auto', md: '232px' }}
        position={{ md: 'sticky' }}
        top="0"
        h={{ md: '100vh' }}
        bg="app.surface"
        borderColor="app.border"
        borderBottomWidth={{ base: '1px', md: 0 }}
        borderRightWidth={{ base: 0, md: '1px' }}
        px="4"
        py={{ base: '3', md: '6' }}
        gap={{ base: '2', md: '6' }}
      >
        <Flex align="center" px="2">
          <CareerBuddyLogo />
        </Flex>
        <SidebarNav />
      </Flex>
      <Box as="main" flex="1" minW="0" px={{ base: '4', md: '10' }} py={{ base: '5', md: '8' }}>
        <Outlet />
      </Box>
    </Flex>
  )
}
