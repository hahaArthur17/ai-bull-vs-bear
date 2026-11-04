import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import App from "../../App";

// BB-006: real screen components, HTTP client and API services; only device
// primitives are adapted to a DOM. run_ui_integration.py owns the test API.
test.skipIf(!process.env.EXPO_PUBLIC_API_URL)(
  "BB-006: research, both Debate rounds, explanation and saved history",
  async () => {
    render(<App />);
    fireEvent.click(
      await screen.findByRole("button", { name: "AAPL, Apple Inc., Research ready" }),
    );
    fireEvent.click(await screen.findByRole("button", { name: /Start Bull vs Bear/ }));
    const explain = await screen.findAllByRole("button", { name: "Explain snapshot" });
    fireEvent.click(explain[0]);
    fireEvent.click(await screen.findByRole("button", { name: "Ask the educational Explainer" }));
    expect(await screen.findByText("EXPLAINER ANSWER")).toBeTruthy();
    fireEvent.click(
      await screen.findByRole("button", { name: "Prepare this question as a Round 2 challenge" }),
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Confirm and start Round 2 with this challenge" }),
    );
    expect(await screen.findByText(/^Final neutral Judge$/i)).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "History" }));
    fireEvent.click(await screen.findByRole("button", { name: "Open AAPL Debate: FINAL JUDGE" }));
    expect(await screen.findByText(/^Final neutral Judge$/i)).toBeTruthy();
  },
);
