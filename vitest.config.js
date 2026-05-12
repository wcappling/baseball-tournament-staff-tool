import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["baseball_aggregator/tests/frontend/**/*.test.js"],
  },
});
