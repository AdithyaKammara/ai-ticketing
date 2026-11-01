import { expect, test } from '@playwright/test'
import { expectAccessible, signInAs } from './helpers.ts'

// The three golden paths from the PRD (section 11). The AI is not called here: the triage
// worker isn't started, so a new ticket stays in Triaging, and the feedback step uses a
// seeded auto-resolved ticket. That keeps these runs deterministic and key-free.

test('requester submits a ticket and rates an automatic answer', async ({ page }) => {
  await signInAs(page, 'Requester')
  await expect(page.getByRole('heading', { name: 'My tickets' })).toBeVisible()
  await expectAccessible(page)

  await page.getByRole('link', { name: 'New ticket' }).click()
  await page.getByLabel('Title').fill('Laptop will not boot')
  await page.getByLabel('Description').fill('Black screen after the logo since this morning.')
  await expectAccessible(page)
  await page.getByRole('button', { name: 'Submit ticket' }).click()

  await expect(page).toHaveURL(/\/tickets\/[0-9a-f-]+$/)
  await expect(page.getByText('Triaging your ticket')).toBeVisible()

  await page.getByRole('link', { name: 'My tickets' }).click()
  await page
    .getByRole('link', { name: /Password reset link expired/ })
    .first()
    .click()
  await expect(page.getByText('Did this solve your problem?')).toBeVisible()
  await expectAccessible(page)
  await page.getByRole('button', { name: 'Yes', exact: true }).click()
  await expect(page.getByText('Thanks for the feedback.')).toBeVisible()
})

test('agent works a ticket to resolved', async ({ page }) => {
  await signInAs(page, 'Agent')
  await expect(page.getByRole('heading', { name: 'Ticket queue' })).toBeVisible()
  await expectAccessible(page)

  await page.goto('/queue?tab=dept&status=IN_PROGRESS')
  await page
    .getByRole('link', { name: /In progress/ })
    .first()
    .click()
  await expect(page.getByLabel('Status')).toBeVisible()
  await expectAccessible(page)

  await page.getByLabel('Reply').fill('Fixed by restarting the reporting job. Please confirm.')
  await page.getByRole('button', { name: 'Send reply' }).click()
  await expect(page.getByText('Fixed by restarting the reporting job.')).toBeVisible()

  await page.getByLabel('Status').selectOption('RESOLVED')
  await expect(page.getByText('Status updated')).toBeVisible()
  await expect(page.locator('span', { hasText: /^Resolved$/ }).first()).toBeVisible()
})

test('admin deactivates an agent and their tickets return to Unassigned', async ({ page }) => {
  await signInAs(page, 'Admin')
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
  await expectAccessible(page)

  await page.goto('/queue?tab=unassigned')
  await expect(page.getByRole('heading', { name: 'Ticket queue' })).toBeVisible()
  const lenasTicket = page.getByRole('link', { name: /Dashboard dates show the wrong timezone/ })
  await expect(lenasTicket).toHaveCount(0)

  await page.getByRole('link', { name: 'Team' }).click()
  await expectAccessible(page)
  page.once('dialog', (dialog) => void dialog.accept())
  await page
    .getByRole('row', { name: /Lena Fischer/ })
    .getByRole('button', { name: 'Deactivate' })
    .click()
  await expect(page.getByText(/went back to Unassigned/)).toBeVisible()

  await page.goto('/queue?tab=unassigned')
  await expect(lenasTicket.first()).toBeVisible()
})
