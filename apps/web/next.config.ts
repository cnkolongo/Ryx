import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: {
    serverActions: {
      allowedOrigins: ["localhost:3000"],
    },
  },
  async rewrites() {
    const gatewayUrl = process.env.GATEWAY_URL || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${gatewayUrl}/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
