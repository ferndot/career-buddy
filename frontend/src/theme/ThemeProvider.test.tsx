import { Text } from '@chakra-ui/react'
import { render, screen } from '@testing-library/react'
import { ThemeProvider } from '.'

describe('ThemeProvider', () => {
  it('renders Chakra components', () => {
    render(
      <ThemeProvider>
        <Text color="app.text">hello</Text>
      </ThemeProvider>,
    )
    expect(screen.getByText('hello')).toBeInTheDocument()
  })
})
