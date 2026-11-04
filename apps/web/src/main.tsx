import "@fontsource-variable/inter";
import "@/styles/globals.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { AppProviders } from "@/app/providers/app-providers";

const root = createRoot(document.getElementById("root")!);
root.render(
  <div
    className="flex min-h-screen items-center justify-center text-sm text-muted-foreground"
    role="status"
  >
    Preparing your workspace…
  </div>,
);

async function startApplication() {
  const { startMocks } = await import("@/mocks/browser/start");
  await startMocks();
  return import("@/app/router/router");
}

startApplication()
  .then(({ router }) => {
    root.render(
      <StrictMode>
        <AppProviders>
          <RouterProvider router={router} />
        </AppProviders>
      </StrictMode>,
    );
  })
  .catch((error: unknown) => {
    root.render(
      <div className="mx-auto max-w-xl px-6 py-24">
        <h1 className="page-title">The workspace needs a moment.</h1>
        <p role="alert" className="my-6 text-sm text-muted-foreground">
          {error instanceof Error ? error.message : "The demo could not start."}
        </p>
        <button
          onClick={() => window.location.reload()}
          className="rounded-lg bg-primary px-4 py-3 text-sm text-primary-foreground"
        >
          Try again
        </button>
      </div>,
    );
  });
