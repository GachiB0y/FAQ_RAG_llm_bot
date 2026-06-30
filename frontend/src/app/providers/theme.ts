import type { ThemeConfig } from '@chakra-ui/react';
import { extendTheme } from '@chakra-ui/react';

const config: ThemeConfig = {
  initialColorMode: 'dark',
  useSystemColorMode: false,
};

const colors = {
  brand: {
    50: '#f0f7ff',
    100: '#d6e4ff',
    200: '#a4c6ff',
    300: '#78a5ff',
    400: '#4f84ff',
    500: '#376aff',
    600: '#264ddb',
    700: '#1b39b7',
    800: '#12258f',
    900: '#0b175c',
  },
  plum: {
    50: '#f6f0ff',
    100: '#e5ccff',
    200: '#d1a3ff',
    300: '#b975ff',
    400: '#a14dff',
    500: '#8732e6',
    600: '#6927b4',
    700: '#4b1d82',
    800: '#2e1253',
    900: '#150629',
  },
};

const semanticTokens = {
  colors: {
    'bg.canvas': { default: '#05060a', _light: '#f8f9fb' },
    'bg.surface': { default: '#101223', _light: '#ffffff' },
    'bg.subtle': { default: '#171a2c', _light: '#f1f3f9' },
    'text.primary': { default: '#f4f6ff', _light: '#0f172a' },
    'text.secondary': { default: '#c1c7df', _light: '#475569' },
    'border.default': { default: '#23263a', _light: '#cfd5e8' },
    'accent.primary': { default: 'brand.400', _light: 'brand.600' },
    'accent.secondary': { default: 'plum.300', _light: 'plum.500' },
  },
  radii: {
    'card.lg': '24px',
  },
  space: {
    'page.gutter': '1.5rem',
  },
};

export const theme = extendTheme({
  config,
  colors,
  semanticTokens,
  styles: {
    global: {
      body: {
        bg: 'bg.canvas',
        color: 'text.primary',
        fontFamily: 'body',
      },
      '*::selection': {
        background: 'accent.secondary',
        color: 'bg.canvas',
      },
    },
  },
  fonts: {
    heading: 'Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif',
    body: 'Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif',
  },
  components: {
    Container: {
      baseStyle: {
        px: { base: 4, md: 6 },
      },
    },
    Button: {
      defaultProps: {
        colorScheme: 'brand',
      },
      variants: {
        ghost: {
          color: 'text.secondary',
          _hover: { color: 'text.primary', bg: 'bg.subtle' },
        },
      },
    },
    Table: {
      baseStyle: {
        th: {
          textTransform: 'none',
          fontWeight: '600',
          color: 'text.secondary',
          fontSize: 'sm',
        },
      },
    },
  },
});
