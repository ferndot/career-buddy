import { Text } from '@chakra-ui/react'
import { render, screen } from '@testing-library/react'
import { ColorModeToggle, ThemeProvider } from '.'

describe('ThemeProvider', () => {
  it('renders Chakra components and the color mode toggle', () => {
    render(
      <ThemeProvider>
        <Text color="app.text">hello</Text>
        <ColorModeToggle />
      </ThemeProvider>,
    )
    expect(screen.getByText('hello')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /switch to (dark|light) mode/i })).toBeInTheDocument()
  })
})
