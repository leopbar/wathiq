import { expect, test, type Page } from "@playwright/test";

/**
 * Screenshots for the README. Not part of the suite: it is skipped unless a folder is given, so
 * CI never depends on it. To refresh them, from the repository root:
 *
 *   docker compose --profile test run --rm -v "$PWD/docs/screenshots:/shots"  *     -e WATHIQ_SHOTS=/shots e2e npx playwright test tests/screenshots.spec.ts
 */
const SHOTS = process.env.WATHIQ_SHOTS ?? "";

async function signInAs(page: Page, title: string) {
  await page.goto("/login");
  await page.getByRole("button", { name: `Sign in as ${title}` }).click();
  await expect(page).toHaveURL(/\/$|\/\?/);
}

// Firefox, not Chromium: headless Chromium has no PDF viewer, so the document preview would
// be a blank rectangle in every screenshot.
test.use({
  browserName: "firefox",
  viewport: { width: 1440, height: 900 },
  launchOptions: { firefoxUserPrefs: { "pdfjs.disabled": false } },
});

test("capture", async ({ page }) => {
  test.skip(!SHOTS, "set WATHIQ_SHOTS to the output folder to capture screenshots");
  test.setTimeout(240_000);
  await page.goto("/login");
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${SHOTS}/01-login.png` });

  await signInAs(page, "Operations Officer");
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${SHOTS}/02-dashboard.png` });

  await page.goto("/cases");
  await page.waitForTimeout(1800);
  await page.screenshot({ path: `${SHOTS}/03-cases.png` });

  // A finished case, so the screenshots show a whole run rather than one still moving.
  await page.getByRole("row").filter({ hasText: "Completed" }).first().click();
  await expect(page).toHaveURL(/\/cases\/[0-9a-f-]{36}/);
  // The document preview loads in an iframe; give it time or the page looks empty.
  await page.waitForTimeout(6000);
  await page.screenshot({ path: `${SHOTS}/04-case-fields.png` });
  await page.getByRole("tab", { name: /Assurance/ }).click();
  await page.waitForTimeout(3500);
  await page.screenshot({ path: `${SHOTS}/05-case-assurance.png` });
  await page.getByRole("tab", { name: /Process/ }).click();
  await page.waitForTimeout(3500);
  await page.screenshot({ path: `${SHOTS}/06-case-process.png` });

  await page.goto("/failures");
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${SHOTS}/07-failure-gallery.png` });

  await page.goto("/cases/new");
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${SHOTS}/08-new-case.png` });

  // Arabic, right-to-left.
  await page.getByRole("button", { name: "التبديل إلى العربية" }).click();
  await page.goto("/");
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${SHOTS}/09-dashboard-arabic.png` });
  await page.goto("/failures");
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${SHOTS}/10-failure-gallery-arabic.png` });
  // Back to English and signed out, for the reviewer's screens.
  await page.evaluate(() => {
    localStorage.setItem("wathiq.lang", "en");
    localStorage.removeItem("wathiq.token");
  });
  await signInAs(page, "Reviewer");
  await page.goto("/review");
  await page.waitForTimeout(1800);
  await page.screenshot({ path: `${SHOTS}/11-review-queue.png` });

  await page.goto("/quality");
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${SHOTS}/12-quality-lab.png` });
});
