import { createBrowserRouter } from "react-router-dom";
import { AppLayout } from "@/app/layout/app-layout";
import { PageLoading } from "@/components/shared/status/page-loading";
import { RouteError } from "./route-error";

export const router = createBrowserRouter([
  {
    Component: AppLayout,
    ErrorBoundary: RouteError,
    HydrateFallback: PageLoading,
    children: [
      {
        index: true,
        lazy: async () => ({
          Component: (await import("@/pages/workbench/workbench-page")).WorkbenchPage,
        }),
      },
      {
        path: "stocks/:ticker",
        lazy: async () => ({
          Component: (await import("@/pages/research/research-page")).ResearchPage,
        }),
      },
      {
        path: "debates/:sessionId",
        lazy: async () => ({ Component: (await import("@/pages/debate/debate-page")).DebatePage }),
      },
      {
        path: "history",
        lazy: async () => ({
          Component: (await import("@/pages/history/history-page")).HistoryPage,
        }),
      },
      {
        path: "user",
        lazy: async () => ({ Component: (await import("@/pages/user/user-page")).UserPage }),
      },
      {
        path: "feedback",
        lazy: async () => ({
          Component: (await import("@/pages/feedback/feedback-page")).FeedbackPage,
        }),
      },
      {
        path: "about",
        lazy: async () => ({ Component: (await import("@/pages/about/about-page")).AboutPage }),
      },
      {
        path: "*",
        lazy: async () => ({
          Component: (await import("@/pages/not-found/not-found-page")).NotFoundPage,
        }),
      },
    ],
  },
]);
