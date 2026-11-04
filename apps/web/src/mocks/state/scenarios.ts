import { clearDemoStorage } from "@/lib/storage";

export type DemoScenario = "normal" | "empty" | "error" | "slow";
let scenario: DemoScenario = "normal";

export function getDemoScenario(): DemoScenario {
  return scenario;
}

export function setDemoScenario(next: DemoScenario): void {
  scenario = next;
}

export function resetDemoState(): void {
  clearDemoStorage();
  scenario = "normal";
}
