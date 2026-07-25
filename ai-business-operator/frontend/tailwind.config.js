/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./pages/**/*.{js,ts,jsx,tsx}', './components/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        status: {
          pending: '#94a3b8',
          working: '#3b82f6',
          done: '#22c55e',
          error: '#ef4444',
          approval: '#f59e0b',
          blocked: '#7f1d1d',
        },
      },
    },
  },
  plugins: [],
};
