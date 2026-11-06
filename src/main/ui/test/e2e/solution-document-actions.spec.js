import { expect, test } from "@playwright/test";

async function chooseCsvFile(page, trigger, file) {
  const pending = page.waitForEvent("filechooser");
  await page.locator(trigger).click();
  await (await pending).setFiles(file);
}

async function setupSolutions(page) {
  const soeid = `pick${Date.now()}`.slice(0, 20);
  expect((await page.request.post('/project-manager/api/auth/register', { data: { soeid, display_name: 'Picker review', password: 'Password123' } })).ok()).toBeTruthy();
  const personal = await page.request.post('/project-manager/api/spaces/personal', { data: {} });
  expect(personal.ok()).toBeTruthy();
  expect((await page.request.post('/project-manager/api/auth/active-space', { data: { space_id: (await personal.json()).space_id } })).ok()).toBeTruthy();
  const program = await page.request.post('/project-manager/api/programs', { data: { program_name: 'Picker program' } });
  expect(program.ok()).toBeTruthy();
  const project = await page.request.post('/project-manager/api/projects', { data: { program_id: (await program.json()).program_id, project_name: 'Picker project' } });
  expect(project.ok()).toBeTruthy();
  const pid = (await project.json()).project_id;
  const create = async (solution_name) => { const r = await page.request.post(`/project-manager/api/projects/${pid}/solutions`, { data: { solution_name, version: '1.0' } }); expect(r.ok()).toBeTruthy(); return r.json(); };
  const first = await create('Picker first');
  const second = await create('Picker second');
  await page.goto('/project-manager/');
  return { first, second };
}

async function openDocuments(page, solution) {
  await page.locator(`[data-action="edit"][data-type="solution"][data-id="${solution.solution_id}"]`).first().click();
  await page.locator('#solution-modal [data-tab="documents"]').click();
  await expect(page.locator('#solution-documents-list')).not.toContainText('Loading documents...');
}

async function selectDocument(page, name = 'picked.txt') {
  const chooserPromise = page.waitForEvent('filechooser');
  await page.locator('#solution-document-upload').click();
  const chooser = await chooserPromise;
  await chooser.setFiles({ name, mimeType: 'text/plain', buffer: Buffer.from('test') });
}

test('file selection is discarded when the solution editor changes', async ({ page }) => {
  const { first, second } = await setupSolutions(page);
  await openDocuments(page, first);
  const chooserPromise = page.waitForEvent('filechooser');
  await page.locator('#solution-document-upload').click();
  const chooser = await chooserPromise;
  await page.locator('#solution-modal-close').click();
  await openDocuments(page, second);
  let writes = 0;
  await page.route('**/api/solutions/*/documents', async (route) => {
    if (route.request().method() === 'POST') writes += 1;
    await route.continue();
  });
  await chooser.setFiles({ name: 'picked.txt', mimeType: 'text/plain', buffer: Buffer.from('test') });
  await page.waitForTimeout(300);
  expect(writes).toBe(0);
  await selectDocument(page, 'new.txt');
  await expect(page.locator('#solution-documents-list')).toContainText('new.txt');
  expect(writes).toBe(1);
});

test('document upload reports a committed write when refresh fails', async ({ page }) => {
  const { first } = await setupSolutions(page);
  await openDocuments(page, first);
  let uploaded = false;
  await page.route(`**/api/solutions/${first.solution_id}/documents`, async (route) => {
    if (route.request().method() === 'POST') {
      const response = await route.fetch();
      uploaded = response.ok();
      await route.fulfill({ response });
    } else if (uploaded) {
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'unavailable' }) });
    } else {
      await route.continue();
    }
  });
  await selectDocument(page);
  await expect(page.locator('#solution-documents-status')).toContainText('Uploaded picked.txt. Unable to refresh documents');
  expect(uploaded).toBe(true);
});

test('an old upload does not interrupt the current solution document list', async ({ page }) => {
  const { first, second } = await setupSolutions(page);
  await openDocuments(page, first);
  let releaseUpload;
  let markUpload;
  const uploadStarted = new Promise((resolve) => { markUpload = resolve; });
  const uploadHeld = new Promise((resolve) => { releaseUpload = resolve; });
  await page.route(`**/api/solutions/${first.solution_id}/documents`, async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    markUpload();
    await uploadHeld;
    await route.fulfill({ status: 201, contentType: 'application/json', body: '{}' });
  });
  await selectDocument(page);
  await uploadStarted;
  await page.locator('#solution-modal-close').click();
  let releaseList;
  let markList;
  const listStarted = new Promise((resolve) => { markList = resolve; });
  const listHeld = new Promise((resolve) => { releaseList = resolve; });
  await page.route(`**/api/solutions/${second.solution_id}/documents`, async (route) => {
    markList();
    await listHeld;
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([{ document_id: 'current', filename: 'current.txt', size_bytes: 1 }]) });
  });
  await page.locator(`[data-action="edit"][data-type="solution"][data-id="${second.solution_id}"]`).first().click();
  await listStarted;
  releaseUpload();
  await page.waitForTimeout(200);
  releaseList();
  await page.locator('#solution-modal [data-tab="documents"]').click();
  await expect(page.locator('#solution-documents-list')).toContainText('current.txt');
  await expect(page.locator('#solution-documents-status')).not.toContainText('Uploaded picked.txt');
});

test('document upload remains visible after same-session token refresh', async ({ page }) => {
  const { first } = await setupSolutions(page);
  await openDocuments(page, first);
  let writes = 0;
  await page.route(`**/api/solutions/${first.solution_id}/documents`, async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    writes += 1;
    if (writes === 1) return route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'expired' }) });
    return route.continue();
  });
  await selectDocument(page, 'refreshed.txt');
  await expect(page.locator('#solution-documents-list')).toContainText('refreshed.txt');
  await expect(page.locator('#solution-documents-status')).toContainText('Uploaded refreshed.txt.');
  expect(writes).toBe(2);
});

test('file selection is discarded after closing and reopening the same solution', async ({ page }) => {
  const { first } = await setupSolutions(page);
  await openDocuments(page, first);
  const chooserPromise = page.waitForEvent('filechooser');
  await page.locator('#solution-document-upload').click();
  const chooser = await chooserPromise;
  await page.locator('#solution-modal-close').click();
  await openDocuments(page, first);
  let writes = 0;
  await page.route(`**/api/solutions/${first.solution_id}/documents`, async (route) => {
    if (route.request().method() === 'POST') writes += 1;
    await route.continue();
  });
  await chooser.setFiles({ name: 'old.txt', mimeType: 'text/plain', buffer: Buffer.from('test') });
  await page.waitForTimeout(300);
  expect(writes).toBe(0);
  await selectDocument(page, 'new.txt');
  await expect(page.locator('#solution-documents-list')).toContainText('new.txt');
  expect(writes).toBe(1);
});

test('delete confirmation cannot act after the solution editor changes', async ({ page }) => {
  const { first, second } = await setupSolutions(page);
  await openDocuments(page, first);
  await selectDocument(page, 'delete-me.txt');
  await expect(page.locator('#solution-documents-list')).toContainText('delete-me.txt');
  let deletes = 0;
  await page.route(`**/api/solutions/${first.solution_id}/documents/*`, async (route) => {
    if (route.request().method() === 'DELETE') deletes += 1;
    await route.continue();
  });
  await page.locator('.solution-document-delete').click();
  await expect(page.locator('#confirm-modal')).toBeVisible();
  await page.locator('#solution-modal-close').dispatchEvent('click');
  await page.locator(`[data-action="edit"][data-type="solution"][data-id="${second.solution_id}"]`).first().dispatchEvent('click');
  await page.locator('#confirm-modal-confirm').click();
  await page.waitForTimeout(300);
  expect(deletes).toBe(0);
  expect((await page.request.get(`/project-manager/api/solutions/${first.solution_id}/documents`)).ok()).toBeTruthy();
  const list = await (await page.request.get(`/project-manager/api/solutions/${first.solution_id}/documents`)).json();
  expect(list.map((item) => item.filename)).toContain('delete-me.txt');
});

test('late delete does not change a different solution editor', async ({ page }) => {
  const { first, second } = await setupSolutions(page);
  await openDocuments(page, first);
  await selectDocument(page, 'delete-me.txt');
  await expect(page.locator('#solution-documents-list')).toContainText('delete-me.txt');
  let releaseDelete;
  let markDelete;
  const deleteStarted = new Promise((resolve) => { markDelete = resolve; });
  const deleteHeld = new Promise((resolve) => { releaseDelete = resolve; });
  await page.route(`**/api/solutions/${first.solution_id}/documents/*`, async (route) => {
    if (route.request().method() !== 'DELETE') return route.continue();
    markDelete();
    await deleteHeld;
    await route.continue();
  });
  await page.locator('.solution-document-delete').click();
  await page.locator('#confirm-modal-confirm').click();
  await deleteStarted;
  await page.locator('#solution-modal-close').click();
  await openDocuments(page, second);
  await expect(page.locator('#solution-documents-status')).toBeEmpty();
  releaseDelete();
  await page.waitForTimeout(300);
  await expect(page.locator('#solution-documents-status')).not.toContainText('Deleted document');
  await expect(page.locator('#solution-documents-list')).toContainText('No documents uploaded.');
});

test('a pending upload prevents a duplicate mutation in the same solution', async ({ page }) => {
  const { first } = await setupSolutions(page);
  await openDocuments(page, first);
  let writes = 0;
  let releaseUpload;
  let markUpload;
  const uploadStarted = new Promise((resolve) => { markUpload = resolve; });
  const uploadHeld = new Promise((resolve) => { releaseUpload = resolve; });
  await page.route(`**/api/solutions/${first.solution_id}/documents`, async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    writes += 1;
    markUpload();
    await uploadHeld;
    await route.continue();
  });
  await selectDocument(page, 'first.txt');
  await uploadStarted;
  await selectDocument(page, 'second.txt');
  await expect(page.locator('#solution-documents-status')).toContainText('A document change is already in progress.');
  expect(writes).toBe(1);
  releaseUpload();
  await expect(page.locator('#solution-documents-list')).toContainText('first.txt');
  expect(writes).toBe(1);
});

test('document downloads use the current session binding', async ({ page }) => {
  const { first } = await setupSolutions(page);
  await openDocuments(page, first);
  await selectDocument(page, 'download-bound.txt');
  await expect(page.locator('#solution-documents-list')).toContainText('download-bound.txt');
  let binding = '';
  await page.route(`**/api/solutions/${first.solution_id}/documents/*/download`, async (route) => {
    binding = route.request().headers()['x-sipm-session'] || '';
    await route.continue();
  });
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'download-bound.txt' }).click();
  expect((await download).suggestedFilename()).toBe('download-bound.txt');
  expect(binding).toMatch(/^[a-f0-9]{64}$/);
});

test('document downloads reject a replacement session', async ({ page }) => {
  const { first } = await setupSolutions(page);
  await openDocuments(page, first);
  await selectDocument(page, 'private-bound.txt');
  await expect(page.locator('#solution-documents-list')).toContainText('private-bound.txt');
  const replacement = await page.context().newPage();
  const soeid = `docnew${Date.now()}`.slice(0, 20);
  expect((await replacement.request.post('/project-manager/api/auth/register', { data: { soeid, display_name: 'Replacement', password: 'Password123' } })).ok()).toBeTruthy();
  const result = page.waitForResponse((response) => response.url().includes('/documents/') && response.url().endsWith('/download'));
  await page.getByRole('button', { name: 'private-bound.txt' }).click();
  expect((await result).status()).toBe(409);
  await expect(page.locator('#auth-screen')).toBeVisible();
  expect((await replacement.request.get('/project-manager/api/auth/me')).ok()).toBeTruthy();
});

test('CSV import rejects a replacement session before writing', async ({ page }) => {
  await setupSolutions(page);
  await page.locator('#csv-actions-toggle').click();
  await page.locator('#projects-upload').click();
  await chooseCsvFile(page, "#csv-dropzone", { name: 'projects.csv', mimeType: 'text/csv', buffer: Buffer.from('project_name\nWrong session') });
  let releaseBackground;
  const heldBackground = new Promise((resolve) => { releaseBackground = resolve; });
  await page.route('**/project-manager/api/**', async (route) => {
    if (new URL(route.request().url()).pathname.endsWith('/projects/import')) return route.continue();
    await heldBackground;
    return route.continue();
  });
  const replacement = await page.context().newPage();
  const soeid = `csvnew${Date.now()}`.slice(0, 20);
  expect((await replacement.request.post('/project-manager/api/auth/register', { data: { soeid, display_name: 'Replacement', password: 'Password123' } })).ok()).toBeTruthy();
  const result = page.waitForResponse((response) => response.url().endsWith('/projects/import'));
  await page.locator('#csv-submit-upload').click();
  expect((await result).status()).toBe(409);
  releaseBackground();
  await expect(page.locator('#auth-screen')).toBeVisible();
  expect((await replacement.request.get('/project-manager/api/auth/me')).ok()).toBeTruthy();
});
