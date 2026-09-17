/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // Proxy /uploads/* to the FastAPI backend so the Next.js dev server can
  // serve uploaded drawings without a separate reverse proxy.
  async rewrites() {
    const apiBase = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
    return [
      { source: "/uploads/:path*", destination: `${apiBase}/uploads/:path*` },
      { source: "/api/:path*", destination: `${apiBase}/api/:path*` },
    ];
  },
};

export default nextConfig;
