const DEFAULT_API_PROXY_TARGET = "http://127.0.0.1:8000";

function normalizeTarget(target) {
  return String(target || DEFAULT_API_PROXY_TARGET).replace(/\/+$/, "");
}

const apiProxyTarget = normalizeTarget(
  process.env.API_PROXY_TARGET || process.env.NEXT_PUBLIC_API_PROXY_TARGET || DEFAULT_API_PROXY_TARGET,
);

/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    NEXT_PUBLIC_API_PROXY_TARGET: apiProxyTarget,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiProxyTarget}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
