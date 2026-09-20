import { expect, test } from "@playwright/test";

async function login(page: import("@playwright/test").Page, role = "Supervisor") {
  await page.goto("/login");
  await page.getByRole("button", { name: `Sign in as ${role}` }).click();
  await expect(page).toHaveURL(/\/$|\/\?/);
}

test("Quality Lab runs all five bands and opens measured results", async ({ page }) => {
  await login(page);
  await page.goto("/quality");
  const response = page.waitForResponse(r => r.url().endsWith("/quality/runs") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Run evaluation", exact: true }).click();
  const batch = await (await response).json();
  expect(batch.runs).toHaveLength(5);
  await expect(page.getByText("Evaluation finished", { exact: true })).toBeVisible();
  const first = page.getByRole("table", { name: "Evaluation runs" }).locator("tbody tr").first();
  await first.click();
  await expect(page.getByRole("dialog").getByText(/golden-1.0.0/)).toBeVisible();
  await expect(page.getByRole("dialog").getByText("passed", { exact: true }).first()).toBeVisible();
  await page.screenshot({ path: "/e2e/playwright-report/m5-quality.png", fullPage: true });
});

test("Prompt Studio links a measured run to the selected version", async ({ page }) => {
  await login(page, "Administrator");
  await page.goto("/prompts");
  await page.getByRole("tab", { name: "Evaluations" }).click();
  await expect(page.getByText(/Wording sensitivity is not measured/)).toBeVisible();
  await page.getByRole("button", { name: "Evaluate this version" }).click();
  await expect(page.getByRole("dialog").getByText(/Prompt sensitivity:/)).toBeVisible();
  await page.screenshot({ path: "/e2e/playwright-report/m5-prompt.png", fullPage: true });
});

test("Golden set downloads through an authenticated request", async ({ page }) => {
  await login(page);
  await page.goto("/quality");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download golden set" }).click();
  expect((await download).suggestedFilename()).toBe("wathiq-golden.zip");
});
