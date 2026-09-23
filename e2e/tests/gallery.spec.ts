import { expect, test, type Page } from "@playwright/test";

/**
 * The failure-mode gallery, driven through the real UI.
 *
 * The point of the screen is that it does not merely describe a failure: it stages one. So the
 * test clicks *Run it* and follows the case it creates, which is the same thing a person does in
 * a demo. It also checks the two honesty properties: a reader who cannot create cases is told so
 * rather than shown a button that would fail, and entries that cannot be staged show the tests
 * that prove them instead.
 */

async function signInAs(page: Page, title: string) {
  await page.goto("/login");
  await page.getByRole("button", { name: `Sign in as ${title}` }).click();
  await expect(page).toHaveURL(/\/$|\/\?/);
}

test.describe("failure gallery", () => {
  test("running a failure creates a real case that is caught", async ({ page }) => {
    await signInAs(page, "Operations Officer");

    await page.getByRole("link", { name: "Failure gallery" }).click();
    await expect(page).toHaveURL(/\/failures$/);

    const card = page.getByRole("article", { name: /tells the AI to approve the case/ });
    await expect(card).toBeVisible();
    await card.getByRole("button", { name: "Run it" }).click();

    const openCase = card.getByRole("link", { name: /Open WTQ-/ });
    await expect(openCase).toBeVisible({ timeout: 30_000 });
    await openCase.click();

    // The case exists, and the shield stopped it rather than obeying the document.
    await expect(page.getByText("Needs review").first()).toBeVisible({ timeout: 60_000 });
    await page.getByRole("tab", { name: /Findings/ }).click();
    await expect(page.getByText(/instruction/i).first()).toBeVisible({ timeout: 30_000 });
  });

  test("an entry that cannot be staged shows the tests that prove it", async ({ page }) => {
    await signInAs(page, "Operations Officer");
    await page.goto("/failures");

    const card = page.getByRole("article", { name: /post the same result twice/ });
    await expect(card.getByText("Proven by tests")).toBeVisible();
    await expect(card.getByText(/test_posting_twice_does_not_post_twice/)).toBeVisible();
    await expect(card.getByRole("button", { name: "Run it" })).toHaveCount(0);
  });

  test("a reader who cannot create cases is told, not shown a dead button", async ({ page }) => {
    await signInAs(page, "Auditor");
    await page.goto("/failures");

    const card = page.getByRole("article", { name: /tells the AI to approve the case/ });
    await expect(card).toBeVisible();
    await expect(card.getByRole("button", { name: "Run it" })).toHaveCount(0);
    await expect(card.getByText(/role cannot create cases/)).toBeVisible();
  });

  test("the gallery reads in Arabic", async ({ page }) => {
    await signInAs(page, "Operations Officer");
    await page.goto("/failures");
    await page.getByRole("button", { name: "التبديل إلى العربية" }).click();

    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(page.getByRole("heading", { name: "معرض الأعطال" })).toBeVisible();
    await expect(page.getByText("مستند يطلب من الذكاء الاصطناعي اعتماد الحالة")).toBeVisible();
    // A raw key on screen would mean a missing Arabic string.
    expect(await page.locator("body").innerText()).not.toMatch(/gallery\.[a-z]/);
  });
});
