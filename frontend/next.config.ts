import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Mol* ships modern ESM that still benefits from being transpiled through
  // our Next pipeline (it references `import.meta.url`, Workers, etc.).
  transpilePackages: ["molstar"],

  // Next 16 enables Turbopack by default. Turbopack already provides empty
  // `fs` / `path` fallbacks for browser bundles, so no module-alias config is
  // needed here — but we declare an explicit (empty) Turbopack block so the
  // build does not bail out on the "webpack config without turbopack config"
  // safety check.
  turbopack: {},

  // Kept for `next build --webpack` and for legacy tooling: Mol* pulls in
  // `fs` / `path` from a couple of dev-only helpers. Webpack chokes when it
  // sees a Node built-in in a client bundle, so we stub them out.
  webpack: (config, { isServer }) => {
    if (!isServer) {
      config.resolve = config.resolve ?? {};
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        path: false,
      };
    }
    return config;
  },
};

export default nextConfig;
