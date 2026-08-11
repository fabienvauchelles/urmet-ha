import { nodeResolve } from "@rollup/plugin-node-resolve";
import typescript from "@rollup/plugin-typescript";
import terser from "@rollup/plugin-terser";

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
