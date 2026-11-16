/** @type {import('next').NextConfig} */
// `*.dev.tsx` pages (the /__gallery component gallery) exist only in `next dev`; production builds never ship them.
const dev = process.env.NODE_ENV !== 'production';
// NEXT_DIST_DIR lets the e2e dev server (:3001) run beside the demo one (:3000) without sharing .next.
const nextConfig = { distDir: process.env.NEXT_DIST_DIR || '.next', output: 'export', trailingSlash: true, images: { unoptimized: true }, agentRules: false, devIndicators: false,
  pageExtensions: dev ? ['dev.tsx', 'tsx', 'ts'] : ['tsx', 'ts'] };
export default nextConfig;
