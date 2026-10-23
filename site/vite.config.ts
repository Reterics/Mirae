import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, type HtmlTagDescriptor, type Plugin } from "vite";

import { SITE } from "./src/site.ts";

/**
 * Strict Content-Security-Policy, injected into the production build only (the dev server
 * needs inline scripts for hot reload). Everything is served from the site's own origin:
 * no CDNs, no third-party fonts, no inline scripts or styles, no eval.
 * GitHub Pages cannot set response headers, so `frame-ancestors` is not available here.
 */
const CSP = [
  "default-src 'none'",
  "script-src 'self'",
  "style-src 'self'",
  "img-src 'self' blob:", // embedded GLB textures decoded through object URLs
  "media-src 'self'",
  "font-src 'self'",
  "connect-src 'self' blob:", // Three.js ImageBitmapLoader fetches those object URLs
  "manifest-src 'self'",
  "base-uri 'none'",
  "form-action 'none'",
  "object-src 'none'",
  "upgrade-insecure-requests",
].join("; ");

const csp = (): Plugin => ({
  name: "mirae-csp",
  apply: "build",
  transformIndexHtml: () => [
    { tag: "meta", attrs: { "http-equiv": "Content-Security-Policy", content: CSP }, injectTo: "head-prepend" },
    { tag: "meta", attrs: { name: "referrer", content: "strict-origin-when-cross-origin" }, injectTo: "head-prepend" },
  ],
});

/**
 * Title, description, theme colour and Open Graph text, from the same source the app uses.
 * Routes live in the URL hash, so this one page serves them all; each page sets its own <title> at runtime.
 */
const head = (): Plugin => {
  const meta = (attrs: Record<string, string>): HtmlTagDescriptor => ({ tag: "meta", attrs, injectTo: "head" });
  return {
    name: "mirae-head",
    transformIndexHtml: () => [
      { tag: "title", children: SITE.title, injectTo: "head" },
      meta({ name: "description", content: SITE.description }),
      meta({ name: "theme-color", content: SITE.themeColor }),
      meta({ property: "og:type", content: "website" }),
      meta({ property: "og:title", content: SITE.title }),
      meta({ property: "og:description", content: SITE.shortDescription }),
    ],
  };
};

/**
 * index.html and the components point at the repo's own brand files (../assets/brand/*), so
 * there are no copies in site/. The build bundles them; in dev the browser normalises the path to /assets/brand/*,
 * which this serves from disk instead of falling back to index.html.
 */
const BRAND_DIR = fileURLToPath(new URL("../assets/brand/", import.meta.url));
const WIRING_DOC = fileURLToPath(new URL("../docs/wiring.md", import.meta.url));
const brandAssets = (): Plugin => ({
  name: "mirae-brand-assets",
  apply: "serve",
  configureServer(server) {
    server.middlewares.use("/assets/brand", (req, res, next) => {
      const file = path.join(BRAND_DIR, path.basename(decodeURIComponent(req.url ?? "")));
      if (!fs.existsSync(file)) {
        next();
        return;
      }
      res.setHeader("Content-Type", file.endsWith(".png") ? "image/png" : "image/jpeg");
      fs.createReadStream(file).pipe(res);
    });
  },
});

export default defineConfig({
  base: "./", // relative asset paths: the site is deployed into a sub-folder whose name isn't known at build time
  plugins: [react(), tailwindcss(), head(), csp(), brandAssets()],
  // Components import the logo straight from the repo's assets/brand/, outside this package.
  // ...and the assembly guide's wiring diagrams read ../docs/wiring.md, so the doc stays their only source.
  server: { fs: { allow: [".", BRAND_DIR, WIRING_DOC] } },
  build: {
    target: "es2022",
    modulePreload: { polyfill: false }, // the polyfill is an inline script
    assetsInlineLimit: 0, // no data: URIs, so img-src/font-src stay 'self'
    cssCodeSplit: false,
  },
});
