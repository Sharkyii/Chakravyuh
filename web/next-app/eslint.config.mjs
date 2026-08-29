import { FlatCompat } from "@eslint/eslintrc";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const currentDirectory = dirname(fileURLToPath(import.meta.url));
const compat = new FlatCompat({ baseDirectory: currentDirectory });

const eslintConfig = [
  ...compat.extends("next/core-web-vitals"),
  {
    ignores: [
    ".next/**",
    ".open-next/**",
    ".wrangler/**",
    "playwright-report/**",
    "test-results/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    ],
  },
];

export default eslintConfig;
