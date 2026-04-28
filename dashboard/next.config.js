/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8199';
    return [
      // Proxy all /api/* requests to Python backend EXCEPT manual-trades
      // which has its own App Router route handler
      {
        source: '/api/trades/:path*',
        destination: `${apiBase}/api/trades/:path*`,
      },
      {
        source: '/api/positions',
        destination: `${apiBase}/api/positions`,
      },
      {
        source: '/api/status',
        destination: `${apiBase}/api/status`,
      },
      {
        source: '/api/config/:path*',
        destination: `${apiBase}/api/config/:path*`,
      },
      {
        source: '/api/action/:path*',
        destination: `${apiBase}/api/action/:path*`,
      },
      {
        source: '/api/data/:path*',
        destination: `${apiBase}/api/data/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;