import { cleanup, configure } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(cleanup);
configure({ asyncUtilTimeout: 5000 });

vi.mock("expo-status-bar", () => ({ StatusBar: () => null }));
vi.mock("expo-constants", () => ({ default: { expoConfig: { extra: {} } } }));
vi.mock("react-native-url-polyfill/auto", () => ({}));
vi.mock("react-native-safe-area-context", async () => {
  const { View } = await import("react-native");
  return {
    SafeAreaProvider: View,
    SafeAreaView: View,
    initialWindowMetrics: null,
    useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
  };
});
vi.mock("react-native-svg", async () => {
  const { createElement } = await import("react");
  const element =
    (tag: string) =>
    ({ accessibilityLabel, accessibilityRole, ...props }: Record<string, unknown>) =>
      createElement(tag, { ...props, "aria-label": accessibilityLabel, role: accessibilityRole });
  return {
    default: element("svg"),
    Circle: element("circle"),
    Defs: element("defs"),
    Line: element("line"),
    LinearGradient: element("linearGradient"),
    Path: element("path"),
    Stop: element("stop"),
    Rect: element("rect"),
    Text: element("text"),
    G: element("g"),
    Polyline: element("polyline"),
  };
});

// Native device storage is the only storage boundary replaced for DOM tests.
vi.mock("@react-native-async-storage/async-storage", () => {
  const records = new Map<string, string>();
  return {
    default: {
      getItem: async (key: string) => records.get(key) ?? null,
      setItem: async (key: string, value: string) => {
        records.set(key, value);
      },
      removeItem: async (key: string) => {
        records.delete(key);
      },
      getAllKeys: async () => [...records.keys()],
      multiRemove: async (keys: string[]) => {
        keys.forEach((key) => records.delete(key));
      },
    },
  };
});
