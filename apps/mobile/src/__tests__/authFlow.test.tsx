import type { Session } from "@supabase/supabase-js";
import { act, fireEvent, render, renderHook, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { AuthScreen } from "../AuthScreen";
import { useWorkspaceAuth } from "../hooks/useWorkspaceAuth";

const auth = vi.hoisted(() => ({
  signInWithPassword: vi.fn(),
  signUp: vi.fn(),
  getSession: vi.fn(),
  onAuthStateChange: vi.fn(),
}));
vi.mock("../supabase", () => ({ supabase: { auth }, isSupabaseConfigured: true }));

test("authentication validates input, prevents repeat submission and shows a recoverable failure", async () => {
  let fail!: () => void;
  auth.signInWithPassword.mockReturnValue(
    new Promise((_resolve, reject) => {
      fail = () => reject(new Error("offline"));
    }),
  );
  render(<AuthScreen />);
  const signIn = screen.getByRole("button", { name: /^Sign in to workspace$/i });
  expect(signIn.getAttribute("aria-disabled")).toBe("true");
  fireEvent.change(screen.getByLabelText(/email address/i), {
    target: { value: "person@example.com" },
  });
  fireEvent.change(screen.getByLabelText(/^password$/i), {
    target: { value: "test-only-password" },
  });
  fireEvent.click(signIn);
  fireEvent.click(signIn);
  expect(auth.signInWithPassword).toHaveBeenCalledTimes(1);
  await act(async () => fail());
  expect(await screen.findByText(/We could not complete that request/)).toBeTruthy();
  expect(
    screen.getByRole("button", { name: /^Sign in to workspace$/i }).getAttribute("aria-disabled"),
  ).not.toBe("true");
});

test("new auth events override a late initial session and reset the old account once", async () => {
  let complete!: (value: { data: { session: Session | null } }) => void;
  let notify!: (event: string, session: Session | null) => void;
  const unsubscribe = vi.fn();
  auth.getSession.mockReturnValue(
    new Promise((resolve) => {
      complete = resolve;
    }),
  );
  auth.onAuthStateChange.mockImplementation((callback) => {
    notify = callback;
    return { data: { subscription: { unsubscribe } } };
  });
  const reset = vi.fn();
  const session = (id: string) => ({ access_token: id, user: { id } }) as Session;
  const { result, unmount } = renderHook(() => useWorkspaceAuth(reset));
  act(() => {
    notify("SIGNED_IN", session("A"));
    notify("SIGNED_IN", session("B"));
  });
  await act(async () => complete({ data: { session: session("A") } }));
  expect(result.current.session?.user.id).toBe("B");
  expect(reset).toHaveBeenCalledTimes(1);
  unmount();
  expect(unsubscribe).toHaveBeenCalledOnce();
});
