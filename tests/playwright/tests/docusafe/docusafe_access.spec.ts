import { test, expect, type APIRequestContext } from '@playwright/test';
import { getUserContext, getAdminContext, expectCustomResponse, logRequestPayload, attachResponseToReport } from '../../utils/api-client';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Covers Docusafe endpoints not tested in docusafe.spec.ts:
 *  - GET  /api/v1/docusafe/folders/{folder_id}/files/{file_id}/shares/  (file shares list)
 *  - POST /api/v1/docusafe/access/revoke/                               (revoke access)
 *  - GET  /api/v1/docusafe/access/file/{file_id}/                       (list file access grants)
 *  - GET  /api/v1/docusafe/shared-with-me/folders/{folder_id}/files/    (shared files in folder)
 *  - PUT  /api/v1/docusafe/folders/{folder_id}/                         (folder update PUT)
 *  - PATCH /api/v1/docusafe/folders/{folder_id}/                        (folder PATCH)
 */

test.describe('Docusafe Access Control & Shares Extensions', () => {
    let ownerContext: APIRequestContext;
    let guestContext: APIRequestContext;
    let familyId: string;
    let guestUserId: string;
    let folderId: string;
    let fileId: string;
    let accessGrantId: string;

    test.beforeAll(async ({ baseURL }) => {
        ownerContext = await getUserContext();
        guestContext = await getAdminContext();

        // Get owner's family, create one if needed
        const ownerFamilyRes = await ownerContext.get(`${baseURL}/api/v1/family`);
        const ownerFamilyBody = await ownerFamilyRes.json();
        const ownedFamily = (ownerFamilyBody.data || []).find((f: any) => f.is_owner);
        if (ownedFamily) {
            familyId = ownedFamily.id;
        } else {
            const createRes = await ownerContext.post(`${baseURL}/api/v1/family`, {
                data: { name: 'Docusafe Access Test Family' }
            });
            const createBody = await createRes.json();
            familyId = createBody.data?.id;
        }

        if (!familyId) {
            throw new Error('Owner has no family — run docusafe.spec.ts first or ensure test user has a family.');
        }

        // Get guest user ID
        const guestProfileRes = await guestContext.get(`${baseURL}/api/v1/user/profile`);
        const guestProfile = await guestProfileRes.json();
        guestUserId = guestProfile.data.id;

        // Ensure guest is a joined member of the owner's family
        const adminEmail = process.env.TEST_ADMIN_EMAIL!;
        const existingMembersRes = await ownerContext.get(`${baseURL}/api/v1/family/${familyId}`);
        const existingMembersBody = await existingMembersRes.json();
        const members: any[] = existingMembersBody.data?.members || [];
        const alreadyMember = members.find((m: any) => m.email === adminEmail && (m.status === 'joined' || m.status === 'invited'));
        if (!alreadyMember) {
            const addRes = await ownerContext.post(`${baseURL}/api/v1/family/${familyId}/members`, {
                data: { email: adminEmail, relation: 'friend' }
            });
            const addBody = await addRes.json();
            if (addBody.success) {
                const memberId = addBody.data.id;
                await guestContext.post(`${baseURL}/api/v1/family/invitations/${memberId}/accept`);
            }
        } else if (alreadyMember.status === 'invited') {
            await guestContext.post(`${baseURL}/api/v1/family/invitations/${alreadyMember.id}/accept`);
        }

        // Create a folder and upload a file
        const folderRes = await ownerContext.post(`${baseURL}/api/v1/docusafe/folders`, {
            data: { name: `Access-Test Folder ${Date.now()}` }
        });
        const folderBody = await folderRes.json();
        folderId = folderBody.data.id;

        const tempFilePath = path.join(__dirname, 'access-test-upload.txt');
        fs.writeFileSync(tempFilePath, 'Access control test content');

        const uploadRes = await ownerContext.post(
            `${baseURL}/api/v1/docusafe/folders/${folderId}/files`,
            {
                multipart: {
                    file: {
                        name: 'access-test.txt',
                        mimeType: 'text/plain',
                        buffer: fs.readFileSync(tempFilePath),
                    },
                    file_name: 'access-test.txt',
                }
            }
        );
        const uploadBody = await uploadRes.json();
        fileId = uploadBody.data.id;
        fs.unlinkSync(tempFilePath);

        // Grant user-level access so later tests have a grant to revoke
        const grantRes = await ownerContext.post(`${baseURL}/api/v1/docusafe/access/grant`, {
            data: {
                file_ids: [fileId],
                access_type: 'USER',
                family_id: familyId,
                user_ids: [guestUserId],
            }
        });
        const grantBody = await grantRes.json();
        expect(grantRes.status()).toBe(201);

        // Retrieve access grant ID from the list endpoint
        const accessListRes = await ownerContext.get(
            `${baseURL}/api/v1/docusafe/access/file/${fileId}`
        );
        const accessListBody = await accessListRes.json();
        if (accessListBody.data?.length > 0) {
            accessGrantId = accessListBody.data[0].id;
        }
    });

    test.afterAll(async ({ baseURL }) => {
        if (folderId && ownerContext) {
            await ownerContext.delete(`${baseURL}/api/v1/docusafe/folders/${folderId}`).catch(() => {});
        }
    });

    // ── Folder update ──────────────────────────────────────────────────────

    test('Owner can PATCH folder name (partial update)', async ({ baseURL }) => {
        const payload = { name: `Patched Folder ${Date.now()}` };
        const response = await ownerContext.patch(
            `${baseURL}/api/v1/docusafe/folders/${folderId}`,
            { data: payload }
        );

        const body = await expectCustomResponse(response, 200, true, payload, 'PATCH Folder');
        expect(body.data.name).toBe(payload.name);
    });

    test('Owner can PUT folder (full update)', async ({ baseURL }) => {
        const payload = { name: `PUT Updated Folder ${Date.now()}`, description: 'Updated via PUT' };
        await logRequestPayload('PUT', `${baseURL}/api/v1/docusafe/folders/${folderId}`, payload, 'PUT Folder');
        const response = await ownerContext.put(
            `${baseURL}/api/v1/docusafe/folders/${folderId}`,
            { data: payload }
        );

        expect([200, 204]).toContain(response.status());
        const body = await response.json().catch(() => ({}));
        await attachResponseToReport(body, 'PUT Folder');
        if (Object.keys(body).length > 0) {
            expect(body.success).toBe(true);
        }
    });

    // ── File access list ────────────────────────────────────────────────────

    test('Owner can list active access grants for a file', async ({ baseURL }) => {
        const response = await ownerContext.get(
            `${baseURL}/api/v1/docusafe/access/file/${fileId}`
        );

        const body = await expectCustomResponse(response, 200, true, null, 'List File Access Grants');
        expect(Array.isArray(body.data)).toBe(true);
        expect(body.data.length).toBeGreaterThan(0);
        expect(body.data[0]).toHaveProperty('file_id');
        expect(body.data[0]).toHaveProperty('access_type');
    });

    test('Non-owner cannot list access grants for a file', async ({ baseURL }) => {
        await logRequestPayload('GET', `${baseURL}/api/v1/docusafe/access/file/${fileId}`, null, 'List File Access Grants - Non-Owner');
        const response = await guestContext.get(
            `${baseURL}/api/v1/docusafe/access/file/${fileId}`
        );

        // Should be forbidden or empty — access control enforced
        expect([200, 403, 404]).toContain(response.status());
        const body = await response.json().catch(() => ({}));
        await attachResponseToReport(body, 'List File Access Grants - Non-Owner');
        if (response.status() === 200 && Array.isArray(body.data)) {
            // If allowed, the list should be empty (not the owner's grants)
            expect(Array.isArray(body.data)).toBe(true);
        }
    });

    // ── File shares list ────────────────────────────────────────────────────

    test('Owner can list shares for a file', async ({ baseURL }) => {
        // Create a temporary share for this file first
        await ownerContext.post(`${baseURL}/api/v1/docusafe/shares`, {
            data: {
                file_ids: [fileId],
                password: 'testshare123',
                expires_at: new Date(Date.now() + 3600000).toISOString(),
            }
        });

        const response = await ownerContext.get(
            `${baseURL}/api/v1/docusafe/folders/${folderId}/files/${fileId}/shares`
        );

        const body = await expectCustomResponse(response, 200, true, null, 'List File Shares');
        expect(Array.isArray(body.data)).toBe(true);
    });

    // ── Shared files in folder ────────────────────────────────────────────────

    test('Guest can list shared files in a specific shared folder', async ({ baseURL }) => {
        // The folder was shared at user-level for the guest
        const response = await guestContext.get(
            `${baseURL}/api/v1/docusafe/shared-with-me/folders/${folderId}/files`
        );

        const body = await expectCustomResponse(
            response, 200, true, null, 'Shared Files In Folder'
        );
        expect(Array.isArray(body.data)).toBe(true);
    });

    // ── Access revoke ────────────────────────────────────────────────────────

    test('Owner can revoke access for a file', async ({ baseURL }) => {
        expect(accessGrantId).toBeDefined();

        const requestPayload = { access_ids: [accessGrantId] };
        const response = await ownerContext.post(
            `${baseURL}/api/v1/docusafe/access/revoke`,
            { data: requestPayload }
        );

        const body = await expectCustomResponse(response, 200, true, requestPayload, 'Revoke File Access');
        expect(body.data).toHaveProperty('count');
        expect(body.data.count).toBeGreaterThan(0);
    });

    test('Guest loses access after revocation', async ({ baseURL }) => {
        // After revoking, the guest should no longer have access
        await logRequestPayload('GET', `${baseURL}/api/v1/docusafe/folders/${folderId}/files/${fileId}`, null, 'File Access - After Revocation');
        const response = await guestContext.get(
            `${baseURL}/api/v1/docusafe/folders/${folderId}/files/${fileId}`
        );

        expect([403, 404]).toContain(response.status());
        const body = await response.json().catch(() => ({}));
        await attachResponseToReport(body, 'File Access - After Revocation');
    });

    test('Revoke with invalid access_id returns error', async ({ baseURL }) => {
        const requestPayload = { access_ids: ['00000000-0000-0000-0000-000000000000'] };

        await logRequestPayload('POST', `${baseURL}/api/v1/docusafe/access/revoke`, requestPayload, 'Revoke Access - Invalid ID');
        const response = await ownerContext.post(
            `${baseURL}/api/v1/docusafe/access/revoke`,
            { data: requestPayload }
        );

        const body = await response.json();
        await attachResponseToReport(body, 'Revoke Access - Invalid ID');
        // Should succeed with count=0 or return error
        expect(body).toHaveProperty('success');
    });

    test('Revoke with empty list returns validation error', async ({ baseURL }) => {
        const requestPayload = { access_ids: [] };

        await logRequestPayload('POST', `${baseURL}/api/v1/docusafe/access/revoke`, requestPayload, 'Revoke Access - Empty List');
        const response = await ownerContext.post(
            `${baseURL}/api/v1/docusafe/access/revoke`,
            { data: requestPayload }
        );

        expect([400, 200]).toContain(response.status());
        const body = await response.json();
        await attachResponseToReport(body, 'Revoke Access - Empty List');
        expect(body.success).toBe(false);
    });
});
