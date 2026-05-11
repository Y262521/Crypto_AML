/** @type {import('next').NextConfig} */
const nextConfig = {
  turbopack: {
    root: import.meta.dirname,
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:3002/api/:path*',
      },
      {
        source: '/ws/:path*',
        destination: 'http://localhost:3002/ws/:path*',
      },
    ]
  },
}

export default nextConfig
