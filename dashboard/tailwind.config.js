/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // GitHub dark palette — flat, no gradients
        bg: '#0d1117',
        surface: '#161b22',
        border: '#30363d',
        'text-primary': '#e6edf3',
        'text-secondary': '#8b949e',
        'text-muted': '#6e7681',
        // Accent colors (flat, no gradients)
        accent: '#58a6ff',
        success: '#3fb950',
        warning: '#d29922',
        danger: '#f85149',
      },
      fontFamily: {
        sans: ['system-ui', '-apple-system', 'sans-serif'],
        mono: ['"SF Mono"', 'Consolas', '"Liberation Mono"', 'monospace'],
      },
      fontSize: {
        '2xs': '10px',
      },
      animation: {
        'slide-in': 'slideInDown 0.2s ease-out',
        'critical-pulse': 'criticalPulse 1.2s ease-in-out infinite',
        'urgent-pulse': 'urgentPulse 1s ease-in-out infinite',
        'skeleton-pulse': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
      },
    },
  },
  plugins: [],
};
