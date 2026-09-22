import { expect, test, type Page } from "@playwright/test";
import { simplePdf } from "./pdf";

/**
 * Use case 2 — salary certificates — driven through the real UI.
 *
 * The second use case was added by configuration: a document type, a rule pack, a prompt and a
 * case-type profile. These tests prove the configuration is what the product actually runs:
 * the certificate is read, the employer is checked against the registry, and an approved case
 * is posted to core banking as an income verification on the employee's own file.
 */

async function signInAs(page: Page, title: string) {
  await page.goto("/login");
  await page.getByRole("button", { name: `Sign in as ${title}` }).click();
  await expect(page).toHaveURL(/\/$|\/\?/);
}

function isoDaysAgo(days: number): string {
  const date = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
  return date.toISOString().slice(0, 10);
}

function certificate(employer: string): Array<[string, string]> {
  return [
    ["Employee name", "Mariam Al Hashimi"],
    ["Employer name", employer],
    ["Designation", "Finance Lead"],
    ["Basic salary", "AED 18,000"],
    ["Total salary", "AED 26,400"],
    ["Issue date", isoDaysAgo(10)],
    ["IBAN", "AE07 0331 2345 6789 0123 456"],
  ];
}

async function runSalaryCase(page: Page, employer: string) {
  await page.goto("/cases/new");
  await page.getByLabel(/Customer name/i).first().fill("Mariam Al Hashimi");
  await page.getByRole("combobox", { name: /Case type/i }).click();
  await page.getByRole("option", { name: /Salary certificate/i }).click();
  await page.setInputFiles('input[type="file"]', {
    name: "salary_certificate.pdf",
    mimeType: "application/pdf",
    buffer: simplePdf("Salary certificate", certificate(employer), "Synthetic demo document"),
  });
  await page.getByRole("button", { name: /Create and start/i }).click();

  const viewCase = page.getByRole("link", { name: /View case/i });
  await expect(viewCase).toBeVisible({ timeout: 30_000 });
  await viewCase.click();
}

test.describe("use case 2: salary certificates", () => {
  test("a clean certificate is posted as an income verification on the employee's file", async ({
    page,
  }) => {
    await signInAs(page, "Operations Officer");
    await runSalaryCase(page, "Oasis Medical Supplies");

    await page.getByRole("tab", { name: "Process" }).click();
    const panel = page.getByRole("region", { name: "Business process" });
    await expect(panel.getByText("process finished")).toBeVisible({ timeout: 60_000 });

    const posting = page.getByRole("region", { name: "Core banking posting" });
    // SIM-INC, not SIM-KYC: the profile chose the record, and the engine never named it.
    await expect(posting.getByText(/SIM-INC-/).first()).toBeVisible();
    await expect(posting.getByText(/SIM-CUS-200001/).first()).toBeVisible();
  });

  test("a certificate from a suspended employer stops for a person", async ({ page }) => {
    await signInAs(page, "Operations Officer");
    await runSalaryCase(page, "Sahara Green Contracting");

    // The finding lives on the Findings tab, which carries a count badge once the case settles.
    const findingsTab = page.getByRole("tab", { name: /Findings/ });
    await expect(findingsTab).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("Needs review").first()).toBeVisible({ timeout: 60_000 });
    await findingsTab.click();
    await expect(
      page.getByText(/The employer is suspended in the registry/).first(),
    ).toBeVisible({ timeout: 30_000 });
  });
});
