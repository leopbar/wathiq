import { expect, test } from "@playwright/test";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";

/**
 * Service-level smoke tests. These do not depend on any UI detail, so they keep working while
 * the interface evolves. The full click-through demo flow lives in demo-flow.spec.ts.
 */
test.describe("services are up", () => {
  test("the API is healthy and connected to the database", async ({ request }) => {
    const response = await request.get(`${API}/healthz`);
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.status).toBe("ok");
    expect(body.db).toBe("ok");
  });

  test("the app reports demo mode", async ({ request }) => {
    const response = await request.get(`${API}/api/v1/settings/mode`);
    expect(response.ok()).toBeTruthy();
    expect((await response.json()).mode).toBe("demo");
  });

  test("the five demo roles are offered", async ({ request }) => {
    const response = await request.get(`${API}/api/v1/auth/demo-users`);
    const roles = (await response.json()).map((user: { role: string }) => user.role);
    expect(roles.sort()).toEqual(
      ["admin", "auditor", "ops_officer", "reviewer", "supervisor"].sort(),
    );
  });

  test("seeded cases exist for the dashboards", async ({ request }) => {
    const login = await request.post(`${API}/api/v1/auth/demo-login`, {
      data: { role: "supervisor" },
    });
    const { access_token: token } = await login.json();
    const cases = await request.get(`${API}/api/v1/cases?size=1`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect((await cases.json()).total).toBeGreaterThanOrEqual(30);
  });

  test("the web app serves the single-page shell", async ({ page }) => {
    const response = await page.goto("/");
    expect(response?.status()).toBeLessThan(400);
    await expect(page).toHaveTitle(/Wathiq/i);
  });
});
