import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#0a0b0f',
        surface: '#12141a',
        elevated: '#1a1d26',
        border: '#1e2028',
        accent: '#6366f1',
      },
    },
  },
  plugins: [],
}
export default config
