import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FeedbackPage } from "@/pages/feedback/feedback-page";

vi.mock("@/app/config/env", () => ({
  config: { dataMode: "demo", feedbackMode: "demo", feedbackApiBaseUrl: "" },
}));

function receiptResponse() {
  return Response.json(
    {
      id: "demo_feedback_test",
      mode: "demo",
      status: "simulated",
      submittedAt: "2026-11-05T00:00:00Z",
      attachmentCount: 0,
    },
    { status: 201 },
  );
}

function renderFeedback() {
  const router = createMemoryRouter(
    [
      { path: "/feedback", element: <FeedbackPage /> },
      { path: "/user", element: <h1>User page</h1> },
    ],
    { initialEntries: ["/feedback"] },
  );
  render(<RouterProvider router={router} />);
  return userEvent.setup();
}

describe("feedback form", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(receiptResponse()));
  });

  it("submits useful anonymous feedback through multipart with an explicit Demo receipt", async () => {
    const user = renderFeedback();
    await user.click(screen.getByRole("button", { name: "Fill sample feedback" }));
    await user.click(screen.getByRole("button", { name: "Try demo submission" }));
    expect(await screen.findByText("You’ve completed the feedback demo.")).toBeVisible();
    const [url, options] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe("/api/feedback");
    const request = options as RequestInit;
    expect(request.headers).not.toHaveProperty("Content-Type");
    const payload = JSON.parse(String((request.body as FormData).get("feedback")));
    expect(payload).toMatchObject({
      category: "suggestion",
      fullName: null,
      email: null,
      wantsReply: false,
    });
    expect(screen.getByText(/Nothing was sent to the developer/)).toBeVisible();
  });

  it("focuses required errors and never sends an invalid draft", async () => {
    const user = renderFeedback();
    await user.click(screen.getByRole("button", { name: "Try demo submission" }));
    expect(await screen.findByText("A few details need your attention")).toBeVisible();
    expect(screen.getByRole("combobox", { name: "Feedback type *" })).toHaveFocus();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("requires an email when a reply is requested without losing the feedback", async () => {
    const user = renderFeedback();
    await user.click(screen.getByRole("button", { name: "Fill sample feedback" }));
    await user.click(screen.getByRole("checkbox", { name: "I’d like a reply" }));
    await user.click(screen.getByRole("button", { name: "Try demo submission" }));
    expect(
      (await screen.findAllByText("Add an email address so we can reply.")).length,
    ).toBeGreaterThan(0);
    expect(screen.getByLabelText("Give it a short title *")).toHaveValue(
      "A side-by-side view for saved research",
    );
    expect(fetch).not.toHaveBeenCalled();
  });

  it("keeps a failed draft available for retry", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(Response.json({}, { status: 500 }));
    const user = renderFeedback();
    await user.click(screen.getByRole("button", { name: "Fill sample feedback" }));
    await user.click(screen.getByRole("button", { name: "Try demo submission" }));
    expect(await screen.findByText("We couldn’t finish this submission")).toBeVisible();
    expect(screen.getByLabelText("Give it a short title *")).toHaveValue(
      "A side-by-side view for saved research",
    );
    await user.click(screen.getByRole("button", { name: "Retry submission" }));
    expect(await screen.findByText("You’ve completed the feedback demo.")).toBeVisible();
  });

  it("confirms leaving a dirty draft and returns to the user page", async () => {
    const user = renderFeedback();
    await user.type(screen.getByLabelText("Give it a short title *"), "My draft idea");
    await user.click(screen.getByRole("link", { name: "Back to user page" }));
    expect(await screen.findByRole("alertdialog")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Keep editing" }));
    expect(screen.getByLabelText("Give it a short title *")).toHaveValue("My draft idea");
    await user.click(screen.getByRole("link", { name: "Back to user page" }));
    await user.click(screen.getByRole("button", { name: "Leave page" }));
    expect(await screen.findByRole("heading", { name: "User page" })).toBeVisible();
  });

  it("ignores a cancelled request's late result and preserves its retry key", async () => {
    let finishFirst: (response: Response) => void = () => {};
    vi.mocked(fetch).mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          finishFirst = resolve;
        }),
    );
    const user = renderFeedback();
    await user.click(screen.getByRole("button", { name: "Fill sample feedback" }));
    await user.click(screen.getByRole("button", { name: "Try demo submission" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    await user.click(screen.getByRole("button", { name: "Cancel submission" }));
    await act(async () => {
      finishFirst(receiptResponse());
    });
    expect(screen.queryByText("You’ve completed the feedback demo.")).not.toBeInTheDocument();
    expect(screen.getByText(/Submission cancelled/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Try demo submission" }));
    expect(await screen.findByText("You’ve completed the feedback demo.")).toBeVisible();
    const first = vi.mocked(fetch).mock.calls[0][1]?.headers as Record<string, string>;
    const second = vi.mocked(fetch).mock.calls[1][1]?.headers as Record<string, string>;
    expect(second["Idempotency-Key"]).toBe(first["Idempotency-Key"]);
  });
});
