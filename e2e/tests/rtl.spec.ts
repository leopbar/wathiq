import { expect, test, type Page } from "@playwright/test";

/**
 * Arabic and right-to-left. Switches the interface to Arabic once, then walks every main screen
 * and checks three things: the document is mirrored, a known Arabic heading is on screen, and no
 * raw translation key (a missing string) leaked into the page.
 *
 * Text that the API sends (finding messages, rule explanations) is still English by design, so
 * these checks only look at interface strings.
 */

/** A raw i18n key on screen means a string is missing from ar.json. */
const LEAKED_KEY =
  /\b(caseDetail|reviewTask|roleSummary|commandPalette|integrationStatus|notFound|pipelineProgress|newCase)\.[a-z]|\b(quality|prompts|settings|about|audit|common|catalog|forbidden|dashboard|cases|review|confidence|stepper|timeline|charts|mermaid|mode|delta)\.[a-z]+[A-Z][A-Za-z]*\b/;

async function signInInArabic(page: Page) {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in as Administrator" }).click();
  await expect(page).toHaveURL(/\/$|\/\?/);
  await page.getByRole("button", { name: "التبديل إلى العربية" }).click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("lang", "ar");
}

async function expectArabicScreen(page: Page, heading: string | RegExp) {
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByText(heading).first()).toBeVisible();
  const text = await page.locator("body").innerText();
  expect(text).not.toMatch(LEAKED_KEY);
}

async function apiGet<T>(page: Page, path: string): Promise<T> {
  return page.evaluate(async (url) => {
    const token = localStorage.getItem("wathiq.token");
    const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
    return response.json();
  }, `/api/v1${path}`);
}

test.describe("Arabic and RTL", () => {
  test("the language switch mirrors the layout and survives a reload", async ({ page }) => {
    await signInInArabic(page);
    await expect(page.getByRole("heading", { name: /مرحباً بعودتك/ })).toBeVisible();
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(page.getByRole("heading", { name: /مرحباً بعودتك/ })).toBeVisible();
  });

  test("the case detail, review queue and a review task are in Arabic", async ({ page }) => {
    await signInInArabic(page);

    const cases = await apiGet<{ items: { id: string }[] }>(page, "/cases?size=1");
    await page.goto(`/cases/${cases.items[0].id}`);
    await expectArabicScreen(page, "كل الحالات");
    await expect(page.getByRole("tab", { name: /الحقول/ })).toBeVisible();
    await page.getByRole("tab", { name: /الضمان/ }).click();
    await expectArabicScreen(page, "كل الحالات");
    await page.getByRole("tab", { name: /العملية/ }).click();
    await expect(page.getByRole("region", { name: "العملية المصرفية" })).toBeVisible();

    await page.goto("/review");
    await expectArabicScreen(page, "قائمة المراجعة");

    const queue = await apiGet<{ items: { id: string }[] }>(page, "/review/queue?size=1");
    test.skip(queue.items.length === 0, "no open review task to open");
    await page.goto(`/review/${queue.items[0].id}`);
    await expectArabicScreen(page, "الحقول والنتائج");
    await expect(page.getByRole("button", { name: /إرسال القرار/ })).toBeVisible();
  });

  test("the Quality Lab, Prompt Studio, audit log and About are in Arabic", async ({ page }) => {
    await signInInArabic(page);

    await page.goto("/quality");
    await expectArabicScreen(page, "مختبر الجودة");
    await expect(page.getByRole("button", { name: "تشغيل التقييم", exact: true })).toBeVisible();

    await page.goto("/prompts");
    await expectArabicScreen(page, "استوديو التوجيهات");

    await page.goto("/audit");
    await expectArabicScreen(page, "سجل التدقيق");
    await expect(page.getByRole("link", { name: /تصدير CSV/ })).toBeVisible();

    await page.goto("/about");
    await expectArabicScreen(page, "عن النظام");
    // Diagrams stay left-to-right: a mirrored flowchart would read backwards.
    const diagram = page.locator(".mermaid-host").first();
    await expect(diagram.locator("xpath=ancestor::*[@dir='ltr'][1]")).toHaveCount(1);
  });

  test("every Settings tab is in Arabic", async ({ page }) => {
    await signInInArabic(page);
    await page.goto("/settings");
    await expectArabicScreen(page, "الإعدادات");

    for (const tab of [
      "أنواع المستندات",
      "المستخدمون",
      "الضمان",
      "العمليات",
      "التكاملات",
      "Azure",
      "الوضع",
    ]) {
      await page.getByRole("tab", { name: tab, exact: true }).click();
      await expect(page.getByRole("tabpanel")).toBeVisible();
      const text = await page.locator("body").innerText();
      expect(text, `tab ${tab}`).not.toMatch(LEAKED_KEY);
    }
    await expect(page.getByText("مفاتيح الميزات")).toBeVisible();
  });

  test("switching back to English restores left-to-right", async ({ page }) => {
    await signInInArabic(page);
    await page.getByRole("button", { name: "Switch to English" }).click();
    await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
    await expect(page.getByRole("heading", { name: /Good to see you/i })).toBeVisible();
  });
});
