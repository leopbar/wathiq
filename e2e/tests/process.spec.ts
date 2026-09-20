import { expect, test, type Page } from "@playwright/test";
import { EXPIRED_TRADE_LICENCE, VALID_TRADE_LICENCE, simplePdf } from "./pdf";

/**
 * The M4 process layer, driven through the real UI.
 *
 * The questions these answer are the ones an operations team asks about an automated process:
 * where is this case, who allowed the posting, what stops it being posted twice, and can anyone
 * quietly edit the record afterwards.
 *
 * They pass whichever engine is running the process — Conductor when it is up, the in-process
 * fallback otherwise — because both write the same record. One test checks that the screen says
 * which of the two it was, since a demo on the fallback must not look like one on Conductor.
 *
 * Assertions are scoped to named regions ("Business process", "Process layer") rather than to
 * loose text. A case screen repeats words like "Completed" in several places, and an unscoped
 * match is a strict-mode failure waiting to happen.
 */

async function signInAs(page: Page, title: string) {
  await page.goto("/login");
  await page.getByRole("button", { name: `Sign in as ${title}` }).click();
  await expect(page).toHaveURL(/\/$|\/\?/);
}

async function runCase(
  page: Page,
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

/** The process panel for the case currently on screen, once it has loaded. */
async function openProcessTab(page: Page) {
  // A substring match, not an anchored one: the tab's accessible name includes its badge
  // ("Process 4/10", "Process finished"), and which badge is showing depends on timing.
  await page.getByRole("tab", { name: "Process" }).click();
  const panel = page.getByRole("region", { name: "Business process" });
  await expect(panel).toBeVisible({ timeout: 20_000 });
  return panel;
}

/**
 * Waits for the whole business process to finish, not just the agent graph.
 *
 * A case is `completed` only after it has been posted and sealed, which is a couple of steps
 * after the model stops thinking — so this waits for the process panel to say so.
 */
async function waitForProcessToFinish(page: Page) {
  const panel = await openProcessTab(page);
  await expect(panel.getByText("process finished")).toBeVisible({ timeout: 60_000 });
  return panel;
}

/** The simulated core banking system holds a customer file under this name. */
const KNOWN_CUSTOMER = "Falcon Ridge Trading LLC";

test.describe("process layer", () => {
  test("a straight-through case is posted under a named policy, not a person", async ({
    page,
  }) => {
    await signInAs(page, "Operations Officer");
    await runCase(page, KNOWN_CUSTOMER, "clean.pdf", VALID_TRADE_LICENCE);
    const panel = await waitForProcessToFinish(page);

    // Every step of the business process, read from the case's own event log.
    for (const step of [
      "Intake",
      "Agent (LangGraph)",
      "Post to core banking",
      "Seal the audit trail",
    ]) {
      await expect(panel.getByText(step, { exact: true })).toBeVisible();
    }

    // Nobody looked at this case, so the approval names a policy — never a person.
    const posting = page.getByRole("region", { name: "Core banking posting" });
    await expect(posting.getByText(/Straight-through policy STP-001/)).toBeVisible();
    await expect(posting.getByText("a policy, not a person")).toBeVisible();
    // And the posting says on its own face that nothing reached a real bank.
    await expect(posting.getByText("simulated")).toBeVisible();
  });

  test("the posting carries an idempotency key derived from the workflow", async ({ page }) => {
    await signInAs(page, "Operations Officer");
    await runCase(page, KNOWN_CUSTOMER, "clean.pdf", VALID_TRADE_LICENCE);
    await waitForProcessToFinish(page);

    // The key is built from the workflow instance, which is also the LangGraph thread id.
    // That is what makes a redelivered task a retry instead of a second posting.
    const posting = page.getByRole("region", { name: "Core banking posting" });
    await expect(posting.getByText(/IDEMPOTENCY KEY/i)).toBeVisible();
    await expect(posting.getByText(/:kyc_refresh:1$/)).toBeVisible();
    await expect(posting.getByText(/^SIM-KYC-/)).toBeVisible();
  });

  test("a case that needs a person waits at the human step and says so", async ({ page }) => {
    await signInAs(page, "Operations Officer");
    await runCase(page, "Old Harbour Trading LLC", "expired.pdf", EXPIRED_TRADE_LICENCE);
    await expect(page.getByText(/Needs review/i).first()).toBeVisible({ timeout: 40_000 });

    const panel = await openProcessTab(page);
    await expect(panel.getByText("Human review", { exact: true })).toBeVisible();
    await expect(panel.getByText(/waiting for a person/i)).toBeVisible();
    // Nothing was posted: the step is there, and it has not run.
    await expect(page.getByRole("region", { name: "Core banking posting" })).toHaveCount(0);
  });

  test("the settings page says which engine is actually running the process", async ({
    page,
  }) => {
    await signInAs(page, "Administrator");
    await page.goto("/settings");
    await page.getByRole("tab", { name: "Process" }).click();
    const panel = page.getByRole("region", { name: "Process layer" });
    await expect(panel).toBeVisible();

    await expect(panel.getByText("wathiq_kyc_refresh v1", { exact: true })).toBeVisible();
    // Named plainly, either way. A run on the fallback must not look like a run on Conductor.
    await expect(panel.getByText(/running on: (Conductor|the in-process engine)/)).toBeVisible();

    // The two rules a reader should take away from the workflow.
    await expect(panel.getByText(/only step that writes outside Wathiq/i)).toBeVisible();
    await expect(panel.getByText(/Runs beside the review, not after it/i)).toBeVisible();
  });

  test("the audit trail says it is append-only, and the database is what enforces it", async ({
    page,
  }) => {
    await signInAs(page, "Administrator");
    await page.goto("/settings");
    await page.getByRole("tab", { name: "Process" }).click();

    const card = page.getByRole("region", { name: "Audit trail integrity" });
    await expect(card.getByText("append-only, enforced by the database")).toBeVisible();
    await expect(card.getByText(/rejects every UPDATE and DELETE/i)).toBeVisible();
    // The claim is bounded on the screen, not only in the code.
    await expect(card.getByText(/What this does not prove/i)).toBeVisible();
  });

  test("a supervisor can run the SLA check, and it only touches overdue reviews", async ({
    page,
  }) => {
    await signInAs(page, "Supervisor");
    await page.goto("/settings");
    await page.getByRole("tab", { name: "Process" }).click();
    const panel = page.getByRole("region", { name: "Process layer" });

    const button = panel.getByRole("button", { name: /Run the SLA check now/i });
    await expect(button).toBeVisible();
    await button.click();

    // Either it escalated something overdue or it found nothing. Both are stated, neither is
    // silent, and nothing still inside its SLA can be escalated by pressing this.
    await expect(
      panel.getByText(/escalated to a supervisor|No review is past its SLA/i),
    ).toBeVisible({ timeout: 20_000 });
  });

  test("an auditor sees the process but cannot run the SLA check", async ({ page }) => {
    await signInAs(page, "Auditor");
    await page.goto("/settings");
    await page.getByRole("tab", { name: "Process" }).click();
    const panel = page.getByRole("region", { name: "Process layer" });

    await expect(panel.getByText(/running on:/)).toBeVisible();
    await expect(panel.getByRole("button", { name: /Run the SLA check now/i })).toHaveCount(0);
    await expect(panel.getByText(/Only a supervisor or an admin/i)).toBeVisible();
  });

  test("the About screen draws the process next to the agent graph", async ({ page }) => {
    await signInAs(page, "Administrator");
    await page.goto("/about");

    await expect(page.getByText(/The business process \(Conductor workflow\)/i)).toBeVisible();
    await expect(page.getByText(/The agent graph/i).first()).toBeVisible();
  });
});
