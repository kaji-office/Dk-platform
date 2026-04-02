import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  // Enable standalone output for Docker/production deployment
  output: 'standalone',

  // Proxy /api calls to backend during development (avoids CORS)
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}/api/:path*`,
      },
    ]
  },
}

export default nextConfig
