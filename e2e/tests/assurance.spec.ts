import { expect, test } from "@playwright/test";
import { POISONED_TRADE_LICENCE, VALID_TRADE_LICENCE, simplePdf } from "./pdf";

/**
 * The M3 assurance story, driven through the real UI.
 *
 * These are the three things a bank actually asks about an AI system: can someone talk it
 * into approving a case, can you show me what it checked, and does it stop when it is not
 * sure. Each test answers one of them by clicking through the product.
 */

async function signInAs(page: import("@playwright/test").Page, title: string) {
  await page.goto("/login");
  await page.getByRole("button", { name: `Sign in as ${title}` }).click();
  await expect(page).toHaveURL(/\/$|\/\?/);
}

async function runCase(
  page: import("@playwright/test").Page,
  customer: string,
  filename: string,
  rows: Array<[string, string]>,
) {
  await page.goto("/cases/new");
  await page.getByLabel(/Customer name/i).first().fill(customer);
  await page.setInputFiles('input[type="file"]', {
    name: filename,
    mimeType: "application/pdf",
    buffer: simplePdf("Trade Licence", rows, "Synthetic demo document"),
  });
  await page.getByRole("button", { name: /Create and start/i }).click();

  const viewCase = page.getByRole("link", { name: /View case/i });
  await expect(viewCase).toBeVisible({ timeout: 30_000 });
  await viewCase.click();
}

test.describe("assurance", () => {
  test("a document that tells the system to approve the case is stopped, not obeyed", async ({
    page,
  }) => {
    await signInAs(page, "Operations Officer");
    await runCase(page, "Quiet Harbour Trading LLC", "poisoned.pdf", POISONED_TRADE_LICENCE);

    // The licence itself is perfectly valid, so only the hidden instruction can have stopped
    // it. If the shield were off, this case would complete straight through.
    await expect(page.getByText(/Needs review/i).first()).toBeVisible({ timeout: 30_000 });

    await page.getByRole("tab", { name: /Findings/ }).click();
    await expect(page.getByText(/Hidden instructions found/i).first()).toBeVisible();
    await expect(page.getByText("SUSPECTED_INJECTION")).toBeVisible();

    // And the case was never approved on the strength of it.
    await expect(page.getByText(/Straight-through/i)).toHaveCount(0);
  });

  test("the assurance tab shows what the agent actually checked", async ({ page }) => {
    await signInAs(page, "Operations Officer");
    await runCase(page, "Evidence Trading LLC", "clean.pdf", VALID_TRADE_LICENCE);
    await expect(page.getByText("Completed").first()).toBeVisible({ timeout: 30_000 });

    await page.getByRole("tab", { name: /Assurance/ }).click();

    // Guardrails ran on the document.
    await expect(page.getByRole("button", { name: /Guardrails/ })).toBeVisible();
    await page.getByRole("button", { name: /Guardrails/ }).click();
    await expect(page.getByText(/no instruction-shaped text found/i)).toBeVisible();

    // A worker was dispatched for the document, and it validated first time.
    await page.getByRole("button", { name: /Supervisor and workers/ }).click();
    await expect(page.getByText(/1 in parallel/i)).toBeVisible();

    // The critic looked at every value.
    await expect(page.getByText(/agreed on all/i)).toBeVisible();

    // The investigator screened the company and recorded the steps. This section opens by
    // default when there is a trail to read, so it is not clicked — clicking would close it.
    const investigation = page.getByRole("tabpanel").filter({ hasText: "Investigation" });
    await expect(investigation.getByText("sanctions.screen_name")).toBeVisible();
    await expect(investigation.getByText(/on the sanctions sample list/)).toBeVisible();
    await expect(investigation.getByText(/no match for/)).toBeVisible();
  });

  test("a reviewer can see why a field scored what it did", async ({ page }) => {
    await signInAs(page, "Operations Officer");
    await runCase(page, "Signals Trading LLC", "signals.pdf", VALID_TRADE_LICENCE);
    await expect(page.getByText("Completed").first()).toBeVisible({ timeout: 30_000 });

    // Selecting a field opens the breakdown behind its confidence.
    await page.getByRole("button", { name: /Licence number/i }).first().click();
    await expect(page.getByText(/Why this confidence/i)).toBeVisible();
    await expect(page.getByText(/Found in the document text/i)).toBeVisible();
    await expect(page.getByText(/exact text found in the document/i)).toBeVisible();
  });

  test("Settings states the least-privilege rules for the tool servers", async ({ page }) => {
    await signInAs(page, "Administrator");
    await page.goto("/settings");
    await page.getByRole("tab", { name: /Assurance/ }).click();

    // Core banking is the only server that can write; the others are read-only. Asserted per
    // card rather than by counting text on the page, so a tooltip's copy of a label cannot
    // change the answer.
    const coreBanking = page
      .locator("div")
      .filter({ hasText: /^Core banking \(simulated\)/ })
      .first();
    await expect(coreBanking).toBeVisible();
    await expect(coreBanking.getByText("can write")).toBeVisible();
    await expect(coreBanking.getByText("post_kyc_refresh")).toBeVisible();

    const sanctions = page
      .locator("div")
      .filter({ hasText: /^Sanctions screening \(simulated\)/ })
      .first();
    await expect(sanctions.getByText("read only")).toBeVisible();
    // The investigator may call screening; nothing but the posting step may call core banking.
    await expect(sanctions.getByText("investigator")).toBeVisible();

    // The versioned rule packs are listed with their rules.
    await expect(page.getByText("trade_license@1.2.0")).toBeVisible();
    await expect(page.getByText("TL_NOT_EXPIRED")).toBeVisible();
  });

  test("the Quality Lab is honest about whether confidence is calibrated", async ({ page }) => {
    await signInAs(page, "Supervisor");
    await page.goto("/quality");
    await expect(page.getByText(/Curve (fitted|not fitted yet)/)).toBeVisible();
    await expect(page.getByText(/Where the ground truth comes from/i)).toBeVisible();
  });
});
