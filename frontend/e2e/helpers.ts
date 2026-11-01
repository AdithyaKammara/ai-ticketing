import AxeBuilder from '@axe-core/playwright'
import { expect, type Page } from '@playwright/test'

export async function signInAs(page: Page, role: 'Requester' | 'Agent' | 'Admin') {
  await page.goto('/login')
  await page.getByRole('button', { name: role, exact: true }).click()
  await expect(page).not.toHaveURL(/\/login/)
}

/** WCAG 2.1 AA scan; serious and critical violations fail the test (PRD section 10). */
export async function expectAccessible(page: Page) {
  const { violations } = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze()
  const blocking = violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => `${v.id}: ${v.help} (${v.nodes.map((n) => n.target.join(' ')).join(', ')})`)
  expect(blocking, blocking.join('\n')).toEqual([])
}
