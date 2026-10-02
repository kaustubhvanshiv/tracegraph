/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      // Obsidian Sentinel design tokens from Stitch
      colors: {
        surface: '#0b1326',
        'surface-dim': '#0b1326',
        'surface-low': '#131b2e',
        'surface-container': '#171f33',
        'surface-high': '#222a3d',
        'surface-highest': '#2d3449',
        'surface-bright': '#31394d',
        'surface-lowest': '#060e20',
        primary: '#4edea3',
        'primary-container': '#10b981',
        'on-primary': '#003824',
        'on-surface': '#dae2fd',
        'on-surface-muted': '#bbcabf',
        outline: '#86948a',
        'outline-variant': '#3c4a42',
        error: '#ffb4ab',
        'error-container': '#93000a',
        secondary: '#ffb95f',
        'secondary-container': '#ee9800',
        tertiary: '#ffb2b7',
        'tertiary-container': '#ff7886',
        // entity-type node colours (from Stitch graph panel)
        'node-user': '#3b82f6',
        'node-host': '#10b981',
        'node-process': '#f59e0b',
        'node-server': '#ef4444',
        'node-file': '#64748b',
        'node-ip': '#8b5cf6',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      borderRadius: {
        DEFAULT: '0.375rem',
        lg: '0.5rem',
        xl: '0.75rem',
        '2xl': '1rem',
      },
      boxShadow: {
        'sentinel-sm': '0 4px 12px rgba(0,0,0,0.3)',
        'sentinel-md': '0 4px 12px rgba(0,0,0,0.3), 0 10px 40px rgba(0,0,0,0.15)',
      },
    },
  },
  plugins: [],
}
