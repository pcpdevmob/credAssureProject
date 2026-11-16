/** @type {import('next').NextConfig} */
// `*.dev.tsx` pages (the /__gallery component gallery) exist only in `next dev`; production builds never ship them.
const dev = process.env.NODE_ENV !== 'production';
const nextConfig = { output: 'export', trailingSlash: true, images: { unoptimized: true }, agentRules: false, devIndicators: false,
  pageExtensions: dev ? ['dev.tsx', 'tsx', 'ts'] : ['tsx', 'ts'] };
export default nextConfig;
