import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: { alias: [{ find: /^react-native$/, replacement: "react-native-web" }] },
  oxc: { jsx: { runtime: "automatic" } },
  test: {
    environment: "jsdom",
    include: ["src/__tests__/*.test.tsx"],
    setupFiles: ["src/__tests__/setup.ts"],
    testTimeout: 15000,
    fileParallelism: false,
    reporters: ["default", "junit"],
    outputFile: { junit: "test-results/ui.xml" },
  },
});
