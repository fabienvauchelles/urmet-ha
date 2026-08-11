import { readFileSync } from "node:fs";

import { nodeResolve } from "@rollup/plugin-node-resolve";
import terser from "@rollup/plugin-terser";
import typescript from "@rollup/plugin-typescript";

// package.json is the card's single version source. The console banner every
// browser prints is emitted here, at build time, so no TypeScript file carries a
// version literal that can drift from the package the bundle was built out of.
const { version } = JSON.parse(readFileSync("./package.json", "utf8"));
const BANNER =
  `console.info("%c URMET-PORTIER-CARD %c ${version} ",` +
  ` "background:#1e88e5;color:#fff;border-radius:3px", "");`;

// One bundled ES module, no code splitting: HACS ships a single Lovelace
// resource loaded with type: module (best-practices-card section 1). The bundle
// is written straight into the integration's www/ directory, the single path the
// integration serves it from and the release workflow ships (DESIGN 4, 6.2), so
// `npm run build`, `make card` and CI all refresh the one committed artifact.
export default {
  input: "src/index.ts",
  output: {
    file: "../custom_components/urmet/www/urmet-portier-card.js",
    format: "es",
    sourcemap: false,
    inlineDynamicImports: true,
    banner: BANNER,
  },
  plugins: [
    nodeResolve(),
    typescript({
      tsconfig: "./tsconfig.json",
      exclude: ["test/**/*", "**/*.test.ts"],
      // outDir must sit under the bundle's directory for the plugin's path check;
      // rollup pipes the emit, nothing extra is written there.
      compilerOptions: {
        declaration: false,
        declarationMap: false,
        sourceMap: false,
        outDir: "../custom_components/urmet/www",
      },
    }),
    terser({ format: { comments: false } }),
  ],
};
