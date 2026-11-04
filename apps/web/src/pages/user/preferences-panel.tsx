import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import config from "@/app/config/env";
import { useTheme } from "@/app/providers/theme-context";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getDemoScenario, setDemoScenario, type DemoScenario } from "@/mocks/state/scenarios";
import { ResetDemoDialog } from "./reset-demo-dialog";

const scenarios: { value: DemoScenario; label: string }[] = [
  { value: "normal", label: "Normal results" },
  { value: "empty", label: "Empty results" },
  { value: "error", label: "Search error" },
  { value: "slow", label: "Slower response" },
];

export function PreferencesPanel() {
  const client = useQueryClient();
  const [scenario, updateScenario] = useState<DemoScenario>(getDemoScenario);
  async function changeScenario(value: string) {
    const selected = scenarios.find((item) => item.value === value);
    if (!selected) return;
    setDemoScenario(selected.value);
    updateScenario(selected.value);
    await client.invalidateQueries({ queryKey: ["stocks"] });
    toast.success("Search experience updated", {
      description: "Return to the workspace to try it.",
    });
  }
  return (
    <Card className="shadow-none">
      <CardHeader>
        <h2 className="section-title">Make it feel familiar.</h2>
        <p className="text-sm text-muted-foreground">
          A few preferences for a more comfortable workspace.
        </p>
      </CardHeader>
      <CardContent className="divide-y">
        <ThemeControl />
        {config.dataMode === "demo" && (
          <div className="flex flex-wrap items-center justify-between gap-4 py-6">
            <div className="max-w-md">
              <Label htmlFor="demo-scenario">Demo search experience</Label>
              <p
                id="scenario-description"
                className="mt-2 text-xs leading-relaxed text-muted-foreground"
              >
                Try an empty result, an interrupted search, or a slower response. Your saved stocks
                stay the same.
              </p>
            </div>
            <Select value={scenario} onValueChange={(value) => void changeScenario(value)}>
              <SelectTrigger
                id="demo-scenario"
                aria-describedby="scenario-description"
                className="w-full sm:w-48"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {scenarios.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
        {config.dataMode === "demo" && (
          <div className="flex flex-wrap items-center justify-between gap-4 pt-6">
            <div>
              <p className="text-sm font-medium">A fresh perspective</p>
              <p className="mt-2 text-xs text-muted-foreground">
                Restore the starting watchlist and sample history.
              </p>
            </div>
            <ResetDemoDialog onReset={() => updateScenario("normal")} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ThemeControl() {
  const { theme, setTheme } = useTheme();
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 pb-6">
      <div>
        <Label htmlFor="appearance">Appearance</Label>
        <p id="appearance-description" className="mt-2 text-xs text-muted-foreground">
          Choose the space that is easiest on your eyes.
        </p>
      </div>
      <Select
        value={theme}
        onValueChange={(value) => {
          if (value === "light" || value === "dark") setTheme(value);
        }}
      >
        <SelectTrigger
          id="appearance"
          aria-describedby="appearance-description"
          className="w-full sm:w-48"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="light">Light</SelectItem>
          <SelectItem value="dark">Dark</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
