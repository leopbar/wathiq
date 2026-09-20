import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { AppShell } from "./layout/AppShell";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import Login from "./screens/Login";
import Dashboard from "./screens/Dashboard";
import Cases from "./screens/Cases";
import NewCase from "./screens/NewCase";
import CaseDetail from "./screens/CaseDetail";
import Review from "./screens/Review";
import ReviewTask from "./screens/ReviewTask";
import QualityLab from "./screens/QualityLab";
import PromptStudio from "./screens/PromptStudio";
import Settings from "./screens/Settings";
import AuditLog from "./screens/AuditLog";
import About from "./screens/About";
import NotFound from "./screens/NotFound";

const router = createBrowserRouter([
  { path: "/login", element: <Login /> },
  {
    element: <AppShell />,
    children: [
      {
        index: true,
        element: (
          <ProtectedRoute capability="dashboard">
            <Dashboard />
          </ProtectedRoute>
        ),
      },
      {
        path: "cases",
        element: (
          <ProtectedRoute capability="cases">
            <Cases />
          </ProtectedRoute>
        ),
      },
      {
        path: "cases/new",
        element: (
          <ProtectedRoute capability="case.create">
            <NewCase />
          </ProtectedRoute>
        ),
      },
      {
        path: "cases/:id",
        element: (
          <ProtectedRoute capability="cases">
            <CaseDetail />
          </ProtectedRoute>
        ),
      },
      {
        path: "review",
        element: (
          <ProtectedRoute capability="review">
            <Review />
          </ProtectedRoute>
        ),
      },
      {
        path: "review/:taskId",
        element: (
          <ProtectedRoute capability="review">
            <ReviewTask />
          </ProtectedRoute>
        ),
      },
      {
        path: "quality",
        element: (
          <ProtectedRoute capability="quality">
            <QualityLab />
          </ProtectedRoute>
        ),
      },
      {
        path: "prompts",
        element: (
          <ProtectedRoute capability="prompts">
            <PromptStudio />
          </ProtectedRoute>
        ),
      },
      {
        path: "settings",
        element: (
          <ProtectedRoute capability="settings">
            <Settings />
          </ProtectedRoute>
        ),
      },
      {
        path: "audit",
        element: (
          <ProtectedRoute capability="audit">
            <AuditLog />
          </ProtectedRoute>
        ),
      },
      {
        path: "about",
        element: (
          <ProtectedRoute capability="about">
            <About />
          </ProtectedRoute>
        ),
      },
      { path: "*", element: <NotFound /> },
    ],
  },
]);

export function App() {
  return <RouterProvider router={router} />;
}
