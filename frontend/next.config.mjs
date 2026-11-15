/** @type {import('next').NextConfig} */
const nextConfig = {
  // Overridable so an e2e suite (if one is added later) can run its own
  // isolated frontend + backend alongside a developer's normal `npm run dev`.
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
