/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Only NEXT_PUBLIC_* values reach the browser bundle. No systeme.io key, no JWT
  // secret, no database URL may ever be added here.
  env: {
    NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000',
  },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
