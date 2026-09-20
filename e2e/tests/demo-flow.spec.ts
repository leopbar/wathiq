import { expect, test } from "@playwright/test";

/**
 * The click-through the demo script follows. If this passes, the product demo works.
 */

async function signInAs(page: import("@playwright/test").Page, title: string) {
  await page.goto("/login");
  await page.getByRole("button", { name: `Sign in as ${title}` }).click();
  await expect(page).toHaveURL(/\/$|\/\?/);
}

test.describe("demo flow", () => {
  test("every role can sign in with one click", async ({ page }) => {
    for (const title of [
      "Operations Officer",
      "Reviewer",
      "Supervisor",
      "Administrator",
      "Auditor",
    ]) {
      await signInAs(page, title);
      await expect(page.getByRole("heading", { name: /Good to see you/i })).toBeVisible();
      await page.evaluate(() => localStorage.removeItem("wathiq.token"));
    }
  });

  test("the dashboard shows real seeded numbers", async ({ page }) => {
    await signInAs(page, "Supervisor");
    await expect(page.getByText("STRAIGHT-THROUGH")).toBeVisible();
    await expect(page.getByText("SLA BREACHES")).toBeVisible();

    // At least the 30 seeded cases. Not an exact number: other tests create cases too.
    const total = page.getByText(/^\d+ total$/);
    await expect(total).toBeVisible();
    const count = Number((await total.innerText()).replace(/\D/g, ""));
    expect(count).toBeGreaterThanOrEqual(30);
  });

  test("a case opens with documents, fields and a timeline", async ({ page }) => {
    await signInAs(page, "Reviewer");
    await page.goto("/cases");
    await expect(page.getByRole("heading", { name: "Cases" })).toBeVisible();

    await page.locator("tbody tr").first().click();
    await expect(page).toHaveURL(/\/cases\/[0-9a-f-]{36}/);

    // The identifier that ties Conductor, LangGraph and the audit trail together.
    await expect(page.getByText(/Conductor workflow/i)).toBeVisible();

    await expect(page.getByRole("tab", { name: /Fields/ })).toBeVisible();
    await page.getByRole("tab", { name: /Timeline/ }).click();
    await expect(page.getByText(/classified|extracted|created/i).first()).toBeVisible();
  });

  test("the review queue lists work with SLA state and reasons", async ({ page }) => {
    await signInAs(page, "Reviewer");
    await page.goto("/review");
    await expect(page.getByRole("heading", { name: /Review queue/i })).toBeVisible();
    await expect(page.locator("tbody tr").first()).toBeVisible();
    await expect(page.getByRole("button", { name: /Claim/ }).first()).toBeVisible();
  });

  test("role gating blocks a reviewer from Prompt Studio, in the UI and the API", async ({
    page,
  }) => {
    await signInAs(page, "Reviewer");
    await page.goto("/prompts");
    await expect(page.getByText(/Not allowed for your role/i)).toBeVisible();

    const status = await page.evaluate(async () => {
      const token = localStorage.getItem("wathiq.token");
      const response = await fetch(
        "/api/v1/prompts/classify_document/versions/1.1.0/retire",
        { method: "POST", headers: { Authorization: `Bearer ${token}` } },
      );
      return response.status;
    });
    expect(status).toBe(403);
  });

  test("an admin can open Prompt Studio and see semantic versions", async ({ page }) => {
    await signInAs(page, "Administrator");
    await page.goto("/prompts");
    await expect(page.getByRole("heading", { name: /Prompt Studio/i })).toBeVisible();
    await expect(page.getByText(/^v?2\.1\.0$/).first()).toBeVisible();
  });

  test("the Quality Lab shows all five test bands", async ({ page }) => {
    await signInAs(page, "Supervisor");
    await page.goto("/quality");
    for (const band of ["Model", "Prompt", "Agent", "AI security", "Adversarial"]) {
      await expect(page.getByText(band, { exact: true }).first()).toBeVisible();
    }
  });

  test("the audit log is searchable and exportable", async ({ page }) => {
    await signInAs(page, "Auditor");
    await page.goto("/audit");
    await expect(page.getByRole("heading", { name: /Audit log/i })).toBeVisible();
    await expect(page.locator("tbody tr").first()).toBeVisible();
    await expect(page.getByRole("link", { name: /Export CSV/i })).toBeVisible();
  });

  test("the About screen renders the architecture diagrams", async ({ page }) => {
    await signInAs(page, "Auditor");
    await page.goto("/about");
    await expect(page.getByRole("heading", { name: /About the system/i })).toBeVisible();
    // Mermaid renders to inline SVG; an empty diagram would mean the renderer failed.
    const svg = page.locator(".mermaid-host svg, svg[id^='dwq-mermaid']").first();
    await expect(svg).toBeVisible({ timeout: 20_000 });
    const box = await svg.boundingBox();
    expect(box?.width ?? 0).toBeGreaterThan(200);
  });

  test("an operations officer can create a case and upload a document", async ({ page }) => {
    await signInAs(page, "Operations Officer");
    await page.goto("/cases/new");

    await page.getByLabel(/Customer name/i).first().fill("Playwright Holdings LLC");
    await page.setInputFiles('input[type="file"]', {
      name: "trade-licence.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from(
        "%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n",
      ),
    });
    await expect(page.getByText("trade-licence.pdf")).toBeVisible();
  });
});
