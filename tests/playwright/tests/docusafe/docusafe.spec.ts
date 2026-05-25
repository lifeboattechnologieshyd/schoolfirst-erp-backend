import { test, expect, type APIRequestContext } from '@playwright/test';
import { getUserContext, getAdminContext, expectCustomResponse } from '../../utils/api-client.js';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test.describe('Docusafe API End-to-End', () => {
    let ownerContext: APIRequestContext;
    let guestContext: APIRequestContext;
    let familyId: string;

    let guestUserId: string;
    let ownerUserId: string;

    test.beforeAll(async () => {
        ownerContext = await getUserContext();
        guestContext = await getAdminContext();

        // Setup: Fetch profiles
        const ownerProfileRes = await ownerContext.get('/api/v1/user/profile');
        const ownerProfile = await ownerProfileRes.json();
        ownerUserId = ownerProfile.data.id;

        // Get owner's family, create one if needed
        const ownerFamilyRes = await ownerContext.get('/api/v1/family');
        const ownerFamilyBody = await ownerFamilyRes.json();
        const ownedFamily = (ownerFamilyBody.data || []).find((f: any) => f.is_owner);
        if (ownedFamily) {
            familyId = ownedFamily.id;
        } else {
            const createRes = await ownerContext.post('/api/v1/family', {
                data: { name: 'Docusafe Test Family' }
            });
            const createBody = await createRes.json();
            familyId = createBody.data?.id;
        }

        const guestProfileRes = await guestContext.get('/api/v1/user/profile');
        const guestProfile = await guestProfileRes.json();
        guestUserId = guestProfile.data.id;

        if (!familyId) {
            throw new Error('User has no family assigned.');
        }

        // Ensure guest is a joined member of the owner's family
        const adminEmail = process.env.TEST_ADMIN_EMAIL!;
        const existingMembersRes = await ownerContext.get(`/api/v1/family/${familyId}`);
        const existingMembersBody = await existingMembersRes.json();
        const members: any[] = existingMembersBody.data?.members || [];
        const alreadyMember = members.find((m: any) => m.email === adminEmail && (m.status === 'joined' || m.status === 'invited'));
        if (!alreadyMember) {
            const addRes = await ownerContext.post(`/api/v1/family/${familyId}/members`, {
                data: { email: adminEmail, relation: 'friend' }
            });
            const addBody = await addRes.json();
            if (addBody.success) {
                const memberId = addBody.data.id;
                await guestContext.post(`/api/v1/family/invitations/${memberId}/accept`);
            }
        } else if (alreadyMember.status === 'invited') {
            await guestContext.post(`/api/v1/family/invitations/${alreadyMember.id}/accept`);
        }
    });

    test('Full Docusafe Flow', async () => {
        let folderId: string;
        let fileId: string;
        let projectionFileId: string;
        let shareId: string;

        // 1. Folder & File Basic CRUD
        await test.step('Folder & File CRUD', async () => {
            const folderPayload = {
                name: `Test Folder ${Date.now()}`,
                description: 'Playwright test folder'
            };

            const folderRes = await ownerContext.post('/api/v1/docusafe/folders', { data: folderPayload });
            const folderBody = await expectCustomResponse(folderRes, 201, true, null, 'Create Folder');
            folderId = folderBody.data.id;

            // Upload File
            const tempFilePath = path.join(__dirname, 'test-upload.txt');
            fs.writeFileSync(tempFilePath, 'Hello Playwright!');
            const uploadRes = await ownerContext.post(`/api/v1/docusafe/folders/${folderId}/files`, {
                multipart: {
                    file: {
                        name: 'test-playwright.txt',
                        mimeType: 'text/plain',
                        buffer: fs.readFileSync(tempFilePath),
                    },
                    file_name: 'test-playwright.txt',
                    description: 'Original description'
                }
            });
            const uploadBody = await expectCustomResponse(uploadRes, 201, true, null, 'Upload File');
            fileId = uploadBody.data.id;

            // File Detail & Update
            const detailRes = await ownerContext.get(`/api/v1/docusafe/folders/${folderId}/files/${fileId}`);
            const detailBody = await expectCustomResponse(detailRes, 200, true, null, 'File Detail');
            expect(detailBody.data.description).toBe('Original description');
            expect(detailBody.data.is_shared).toBe(false);
            expect(typeof detailBody.data.file_url).toBe('string');
            expect(detailBody.data.file_url).toBeTruthy();
            expect(typeof detailBody.data.file_url_expiry).toBe('string');
            expect(Date.parse(detailBody.data.file_url_expiry)).not.toBeNaN();
            expect(new Date(detailBody.data.file_url_expiry).getTime()).toBeGreaterThan(Date.now());

            const updatePayload = { description: 'Updated description', file_name: 'renamed-playwright.txt' };
            const updateRes = await ownerContext.patch(`/api/v1/docusafe/folders/${folderId}/files/${fileId}`, { data: updatePayload });
            await expectCustomResponse(updateRes, 200, true, updatePayload, 'Update File (including rename)');

            // Verify rename
            const renamedDetailRes = await ownerContext.get(`/api/v1/docusafe/folders/${folderId}/files/${fileId}`);
            const renamedDetailBody = await renamedDetailRes.json();
            expect(renamedDetailBody.data.file_name).toBe('renamed-playwright.txt');
            expect(typeof renamedDetailBody.data.file_url_expiry).toBe('string');
            expect(Date.parse(renamedDetailBody.data.file_url_expiry)).not.toBeNaN();

            // --- Unique Constraint Check ---
            const duplicateUploadRes = await ownerContext.post(`/api/v1/docusafe/folders/${folderId}/files`, {
                multipart: {
                    file: {
                        name: 'renamed-playwright.txt',
                        mimeType: 'text/plain',
                        buffer: fs.readFileSync(tempFilePath),
                    },
                    file_name: 'renamed-playwright.txt'
                }
            });
            const duplicateBody = await duplicateUploadRes.json();
            expect(duplicateUploadRes.status()).toBe(400);
            expect(duplicateBody.success).toBe(false);
            expect(duplicateBody.error.details[0].message).toContain('already exists');

            const secondUploadRes = await ownerContext.post(`/api/v1/docusafe/folders/${folderId}/files`, {
                multipart: {
                    file: {
                        name: 'second-playwright.txt',
                        mimeType: 'text/plain',
                        buffer: fs.readFileSync(tempFilePath),
                    },
                    file_name: 'second-playwright.txt',
                    description: 'Second file for rename conflict test'
                }
            });
            const secondUploadBody = await expectCustomResponse(secondUploadRes, 201, true, null, 'Upload Second File');
            projectionFileId = secondUploadBody.data.id;

            const duplicateRenameRes = await ownerContext.patch(
                `/api/v1/docusafe/folders/${folderId}/files/${secondUploadBody.data.id}`,
                { data: { file_name: 'renamed-playwright.txt' } }
            );
            const duplicateRenameBody = await duplicateRenameRes.json();
            expect(duplicateRenameRes.status()).toBe(400);
            expect(duplicateRenameBody.success).toBe(false);
            expect(duplicateRenameBody.error.details[0].message).toContain('already exists');

            fs.unlinkSync(tempFilePath);
        });

        // 1.1 Bulk File Upload
        await test.step('Bulk File Upload', async () => {
            const file1Path = path.join(__dirname, 'test-bulk-1.txt');
            const file2Path = path.join(__dirname, 'test-bulk-2.txt');
            fs.writeFileSync(file1Path, 'Bulk File 1 Content');
            fs.writeFileSync(file2Path, 'Bulk File 2 Content');

            // Test 1: Bulk upload fails without descriptions
            const failUploadRes = await ownerContext.post(`/api/v1/docusafe/folders/${folderId}/files/bulk`, {
                multipart: {
                    file1: {
                        name: 'bulk-1.txt',
                        mimeType: 'text/plain',
                        buffer: fs.readFileSync(file1Path),
                    }
                }
            });
            await expectCustomResponse(failUploadRes, 400, false, null, 'Descriptions are mandatory');

            // Test 2: Successful bulk upload with mandatory JSON descriptions
            const descriptions = JSON.stringify([
                { file_name: 'bulk-1.txt', description: 'Description for bulk 1' },
                { file_name: 'bulk-2.txt', description: 'Description for bulk 2' }
            ]);

            const bulkUploadRes = await ownerContext.post(`/api/v1/docusafe/folders/${folderId}/files/bulk`, {
                multipart: {
                    descriptions: descriptions,
                    file1: {
                        name: 'bulk-1.txt',
                        mimeType: 'text/plain',
                        buffer: fs.readFileSync(file1Path),
                    },
                    file2: {
                        name: 'bulk-2.txt',
                        mimeType: 'text/plain',
                        buffer: fs.readFileSync(file2Path),
                    }
                }
            });

            const bulkBody = await expectCustomResponse(bulkUploadRes, 201, true, null, 'Bulk Upload Files');
            expect(bulkBody.data.success_files.length).toBe(2);
            const names = bulkBody.data.success_files.map((f: any) => f.file_name);
            expect(names).toContain('bulk-1.txt');
            expect(names).toContain('bulk-2.txt');

            // Verify descriptions are saved and llm_status is present
            const f1 = bulkBody.data.success_files.find((f: any) => f.file_name === 'bulk-1.txt');
            expect(f1).toBeDefined();
            expect(f1.description).toBe('Description for bulk 1');
            expect(f1.llm_status).toBe('PENDING'); // Verify default llm_status

            // Test 3: Global ParseError handler (Malformed JSON in a POST request)
            // We'll use the folder creation endpoint for this as it's simple
            const malformedRes = await ownerContext.post('/api/v1/docusafe/folders', {
                headers: { 'Content-Type': 'application/json' },
                data: '{ "name": "bad json", }' // Extra comma for malformed JSON
            });
            // Should be 400 Bad Request, not 500
            await expectCustomResponse(malformedRes, 400, false, null, 'Malformed JSON check');

            // Verify folder stats updated
            const folderRes = await ownerContext.get(`/api/v1/docusafe/folders/${folderId}`);
            const folderBody = await folderRes.json();
            // We have 2 files from previous steps + 2 from bulk = 4
            expect(folderBody.data.file_count).toBe(4);

            fs.unlinkSync(file1Path);
            fs.unlinkSync(file2Path);
        });

        // 2. Access Control & Sharing
        await test.step('Access Control & Internal Sharing', async () => {
            // Unauthorized File Retrieve
            const guestDownloadRes = await guestContext.get(`/api/v1/docusafe/folders/${folderId}/files/${fileId}`);
            expect(guestDownloadRes.status()).toBe(403);

            // User-level Sharing
            const sharePayload = {
                file_ids: [fileId],
                access_type: 'USER',
                family_id: familyId,
                user_ids: [guestUserId]
            };
            const shareRes = await ownerContext.post('/api/v1/docusafe/access/grant', { data: sharePayload });
            await expectCustomResponse(shareRes, 201, true, null, 'Grant User Access');

            // Verify Shared With Me
            const sharedWithMeRes = await guestContext.get('/api/v1/docusafe/shared-with-me');
            const sharedWithMeBody = await expectCustomResponse(sharedWithMeRes, 200, true, null, 'Shared With Me');
            expect(sharedWithMeBody.data.some((f: any) => f.id === folderId)).toBe(true);

            // Guest File Retrieve Success (includes file_url)
            const guestDownloadSuccessRes = await guestContext.get(`/api/v1/docusafe/folders/${folderId}/files/${fileId}`);
            const guestDownloadSuccessBody = await expectCustomResponse(guestDownloadSuccessRes, 200, true, null, 'Guest File Retrieve Success');
            expect(typeof guestDownloadSuccessBody.data.file_url).toBe('string');
            expect(guestDownloadSuccessBody.data.file_url).toBeTruthy();

            // --- Security: Family Access Verification ---
            // Upload a NEW file for this test to avoid inheriting any USER grants
            const securityFilePath = path.join(__dirname, 'test-security.txt');
            fs.writeFileSync(securityFilePath, 'Security check content');
            const secRes = await ownerContext.post(`/api/v1/docusafe/folders/${folderId}/files`, {
                multipart: {
                    file: {
                        name: 'security-test.txt',
                        mimeType: 'text/plain',
                        buffer: fs.readFileSync(securityFilePath),
                    },
                    file_name: 'security-test.txt'
                }
            });
            const secBody = await secRes.json();
            const secFileId = secBody.data.id;

            // Grant FAMILY access to a DIFFERENT family (random UUID)
            const randomFamilyId = '00000000-0000-0000-0000-000000000000';
            const randomGrantRes = await ownerContext.post('/api/v1/docusafe/access/grant', {
                data: {
                    file_ids: [secFileId],
                    access_type: 'FAMILY',
                    family_id: randomFamilyId
                }
            });
            await expectCustomResponse(randomGrantRes, 201, true, null, 'Grant Random Family Access');

            // Try to retrieve with guestContext (NOT the owner, same family as owner but doesn't match the random grant)
            const unauthorizedDownloadRes = await guestContext.get(`/api/v1/docusafe/folders/${folderId}/files/${secFileId}`);
            expect(unauthorizedDownloadRes.status()).toBe(403);

            fs.unlinkSync(securityFilePath);
        });

        // 3. Temporary Sharing Management
        await test.step('Temporary Sharing Management', async () => {
            const sharePassword = 'secure123';
            const createPayload = {
                file_ids: [fileId],
                password: sharePassword,
                expires_at: new Date(Date.now() + 3600000).toISOString(),
                max_views: 5
            };

            const createRes = await ownerContext.post('/api/v1/docusafe/shares', { data: createPayload });
            const createBody = await expectCustomResponse(createRes, 201, true, null, 'Create Temp Share');
            shareId = createBody.data.id;

            // Verify is_shared flag
            const fileDetailRes = await ownerContext.get(`/api/v1/docusafe/folders/${folderId}/files/${fileId}`);
            const fileDetail = await fileDetailRes.json();
            expect(fileDetail.data.is_shared).toBe(true);
            expect(typeof fileDetail.data.file_url_expiry).toBe('string');
            expect(Date.parse(fileDetail.data.file_url_expiry)).not.toBeNaN();

            // Update Share (Password and Files)
            const updateSharePayload = {
                password: 'newpassword123',
                files: [{ id: fileId }] // Pass list of objects
            };
            const updateShareRes = await ownerContext.patch(`/api/v1/docusafe/shares/${shareId}`, { data: updateSharePayload });
            await expectCustomResponse(updateShareRes, 200, true, null, 'Update Share Password and Files');

            // Verify detail contains files with file_id and views
            const detailRes = await ownerContext.get(`/api/v1/docusafe/shares/${shareId}`);
            const detailBody = await expectCustomResponse(detailRes, 200, true, null, 'Verify Share Detail Consolidation');
            expect(detailBody.data.files).toBeDefined();
            expect(detailBody.data.files.length).toBe(1);
            expect(detailBody.data.files[0].file_id).toBe(fileId); // Verify file_id in share response
            expect(detailBody.data.views).toBeDefined();

            // Public Access Failure (Wrong Password)
            const failRes = await ownerContext.post(`/api/v1/docusafe/shares/access/${shareId}`, { data: { password: 'wrong' } });
            expect(failRes.status()).toBe(400);

            // Verify detail now has a view log
            const detailWithViewRes = await ownerContext.get(`/api/v1/docusafe/shares/${shareId}`);
            const detailWithViewBody = await detailWithViewRes.json();
            expect(detailWithViewBody.data.views.length).toBeGreaterThan(0);
            expect(detailWithViewBody.data.views[0].success).toBe(false);

            // 3. Public Access Success (New Password)
            const successRes = await ownerContext.post(`/api/v1/docusafe/shares/access/${shareId}`, { data: { password: 'newpassword123' } });
            const successBody = await expectCustomResponse(successRes, 200, true, null, 'Public Access Success');
            expect(successBody.data.files[0].download_url).toBeUndefined(); // verify list API only returns metadata
            expect(successBody.data.title).toBeDefined();
            expect(successBody.data.shared_by).toBeDefined();


            // 3.1 Verify Download Endpoint and View Counts
            const initialShareRes = await ownerContext.get(`/api/v1/docusafe/shares/${shareId}`);
            const initialShareBody = await initialShareRes.json();
            const initialViewCount = initialShareBody.data.view_count;

            const downloadRes = await ownerContext.post(`/api/v1/docusafe/shares/access/${shareId}/files/${fileId}/download`, { data: { password: 'newpassword123' } });
            const downloadBody = await expectCustomResponse(downloadRes, 200, true, null, 'Public Access Download');
            expect(downloadBody.data.download_url).toBeDefined();
            expect(downloadBody.data.expires_in_seconds).toBe(300);

            // Verify view_count didn't inflate
            const postDownloadShareRes = await ownerContext.get(`/api/v1/docusafe/shares/${shareId}`);
            const postDownloadShareBody = await postDownloadShareRes.json();
            expect(postDownloadShareBody.data.view_count).toBe(initialViewCount);

            // 3.2 Client metadata validation and brute-force blocking on a dedicated share
            const guardedShareRes = await ownerContext.post('/api/v1/docusafe/shares', {
                data: {
                    file_ids: [fileId],
                    password: 'guarded123',
                    expires_at: new Date(Date.now() + 86400000).toISOString(),
                    max_failed_attempts: 2
                }
            });
            const guardedShareBody = await expectCustomResponse(guardedShareRes, 201, true, null, 'Create Guarded Share');
            const guardedShareId = guardedShareBody.data.id;

            const invalidMetadataRes = await ownerContext.post(`/api/v1/docusafe/shares/access/${guardedShareId}`, {
                data: {
                    password: 'guarded123',
                    client_metadata: ['invalid']
                }
            });
            const invalidMetadataBody = await invalidMetadataRes.json();
            expect(invalidMetadataRes.status()).toBe(400);
            expect(invalidMetadataBody.success).toBe(false);
            expect(invalidMetadataBody.error.details[0].message).toContain('client_metadata must be a JSON object');

            const oversizedMetadataRes = await ownerContext.post(`/api/v1/docusafe/shares/access/${guardedShareId}`, {
                data: {
                    password: 'guarded123',
                    client_metadata: {
                        blob: 'x'.repeat(2300)
                    }
                }
            });
            const oversizedMetadataBody = await oversizedMetadataRes.json();
            expect(oversizedMetadataRes.status()).toBe(400);
            expect(oversizedMetadataBody.success).toBe(false);
            expect(oversizedMetadataBody.error.details[0].message).toContain('client_metadata must be at most');

            const firstWrongPasswordRes = await ownerContext.post(`/api/v1/docusafe/shares/access/${guardedShareId}`, {
                data: { password: 'wrong-password' }
            });
            const firstWrongPasswordBody = await firstWrongPasswordRes.json();
            expect(firstWrongPasswordRes.status()).toBe(400);
            expect(firstWrongPasswordBody.error.details[0].message).toContain('1 attempts remaining');

            const secondWrongPasswordRes = await ownerContext.post(`/api/v1/docusafe/shares/access/${guardedShareId}`, {
                data: { password: 'wrong-password' }
            });
            const secondWrongPasswordBody = await secondWrongPasswordRes.json();
            expect(secondWrongPasswordRes.status()).toBe(400);
            expect(secondWrongPasswordBody.error.details[0].message).toContain('blocked due to too many failed attempts');

            const blockedShareAccessRes = await ownerContext.post(`/api/v1/docusafe/shares/access/${guardedShareId}`, {
                data: { password: 'guarded123' }
            });
            const blockedShareAccessBody = await blockedShareAccessRes.json();
            expect(blockedShareAccessRes.status()).toBe(400);
            expect(blockedShareAccessBody.error.details[0].message).toContain('This share is blocked');

            const guardedShareDetailRes = await ownerContext.get(`/api/v1/docusafe/shares/${guardedShareId}`);
            const guardedShareDetailBody = await guardedShareDetailRes.json();
            expect(guardedShareDetailBody.data.status).toBe('BLOCKED');
            expect(guardedShareDetailBody.data.failed_attempts).toBe(2);
            expect(guardedShareDetailBody.data.views.length).toBeGreaterThanOrEqual(3);

            const projectionShareRes = await ownerContext.post('/api/v1/docusafe/shares', {
                data: {
                    file_ids: [projectionFileId],
                    password: 'projection123',
                    expires_at: new Date(Date.now() + 86400000).toISOString(),
                    max_failed_attempts: 1
                }
            });
            const projectionShareBody = await expectCustomResponse(
                projectionShareRes,
                201,
                true,
                null,
                'Create Projection Guarded Share'
            );

            const projectionFileBeforeBlockRes = await ownerContext.get(
                `/api/v1/docusafe/folders/${folderId}/files/${projectionFileId}`
            );
            const projectionFileBeforeBlockBody = await projectionFileBeforeBlockRes.json();
            expect(projectionFileBeforeBlockBody.data.is_shared).toBe(true);

            const projectionBlockedRes = await ownerContext.post(
                `/api/v1/docusafe/shares/access/${projectionShareBody.data.id}`,
                { data: { password: 'wrong-password' } }
            );
            const projectionBlockedBody = await projectionBlockedRes.json();
            expect(projectionBlockedRes.status()).toBe(400);
            expect(projectionBlockedBody.error.details[0].message).toContain(
                'blocked due to too many failed attempts'
            );

            const projectionFileAfterBlockRes = await ownerContext.get(
                `/api/v1/docusafe/folders/${folderId}/files/${projectionFileId}`
            );
            const projectionFileAfterBlockBody = await projectionFileAfterBlockRes.json();
            expect(projectionFileAfterBlockBody.data.is_shared).toBe(false);

            const expiringShareRes = await ownerContext.post('/api/v1/docusafe/shares', {
                data: {
                    file_ids: [projectionFileId],
                    password: 'expiresoon123',
                    expires_at: new Date(Date.now() + 1200).toISOString(),
                }
            });
            const expiringShareBody = await expectCustomResponse(
                expiringShareRes,
                201,
                true,
                null,
                'Create Expiring Share'
            );

            const projectionFileBeforeExpiryRes = await ownerContext.get(
                `/api/v1/docusafe/folders/${folderId}/files/${projectionFileId}`
            );
            const projectionFileBeforeExpiryBody = await projectionFileBeforeExpiryRes.json();
            expect(projectionFileBeforeExpiryBody.data.is_shared).toBe(true);

            await new Promise((resolve) => setTimeout(resolve, 1500));

            const expiredShareAccessRes = await ownerContext.post(
                `/api/v1/docusafe/shares/access/${expiringShareBody.data.id}`,
                { data: { password: 'expiresoon123' } }
            );
            const expiredShareAccessBody = await expiredShareAccessRes.json();
            expect(expiredShareAccessRes.status()).toBe(400);
            expect(expiredShareAccessBody.error.details[0].message).toContain('This share has expired');

            const expiredShareDetailRes = await ownerContext.get(
                `/api/v1/docusafe/shares/${expiringShareBody.data.id}`
            );
            const expiredShareDetailBody = await expiredShareDetailRes.json();
            expect(expiredShareDetailBody.data.status).toBe('EXPIRED');

            const projectionFileAfterExpiryRes = await ownerContext.get(
                `/api/v1/docusafe/folders/${folderId}/files/${projectionFileId}`
            );
            const projectionFileAfterExpiryBody = await projectionFileAfterExpiryRes.json();
            expect(projectionFileAfterExpiryBody.data.is_shared).toBe(false);

            // 4. Test Update with Empty File List (Should delete the share)
            // Create a fresh share for this test to avoid affecting shareId used in next step
            const tempRes = await ownerContext.post('/api/v1/docusafe/shares', {
                data: {
                    file_ids: [fileId],
                    password: 'temppassword123',
                    expires_at: new Date(Date.now() + 86400000).toISOString(),
                }
            });
            const tempShare = await tempRes.json();
            const tempShareId = tempShare.data.id;

            const emptyUpdateRes = await ownerContext.patch(`/api/v1/docusafe/shares/${tempShareId}`, { data: { files: [] } });
            const emptyUpdateBody = await expectCustomResponse(emptyUpdateRes, 200, true, null, 'Update Share with Empty Files');
            expect(emptyUpdateBody.data.status).toBe('DELETED');
            expect(emptyUpdateBody.data.message).toContain('deleted because it became empty');
        });

        // 4. Deletion & Cascades (Soft-Delete & Share Sync)
        await test.step('Deletion & Cascades', async () => {
            // Verify share has the file
            const initialShareRes = await ownerContext.get(`/api/v1/docusafe/shares/${shareId}`);
            const initialShare = await initialShareRes.json();
            expect(initialShare.data.file_count).toBe(1);
            expect(initialShare.data.files[0].id).toBe(fileId);

            // Delete Individual File (Soft-Delete)
            const deleteFileRes = await ownerContext.delete(`/api/v1/docusafe/folders/${folderId}/files/${fileId}`);
            await expectCustomResponse(deleteFileRes, 200, true, null, 'Delete File');

            // 1. Verify file is gone from folder list
            const folderFilesRes = await ownerContext.get(`/api/v1/docusafe/folders/${folderId}/files`);
            const folderFiles = await folderFilesRes.json();
            expect(folderFiles.data.some((f: any) => f.id === fileId)).toBe(false);

            // 2. Verify file detail is 404
            const fileDetailAfterDeleteRes = await ownerContext.get(`/api/v1/docusafe/folders/${folderId}/files/${fileId}`);
            expect(fileDetailAfterDeleteRes.status()).toBe(404);

            // 3. Verify share is updated (Share Sync Hook - Deleted because empty)
            const updatedShareRes = await ownerContext.get(`/api/v1/docusafe/shares/${shareId}`);
            expect(updatedShareRes.status()).toBe(404);

            // Cleanup Folder (Soft-Delete)
            const deleteFolderRes = await ownerContext.delete(`/api/v1/docusafe/folders/${folderId}`);
            await expectCustomResponse(deleteFolderRes, 200, true, null, 'Delete Folder');

            // Verify folder is gone from list
            const folderListRes = await ownerContext.get('/api/v1/docusafe/folders');
            const folderList = await folderListRes.json();
            expect(folderList.data.some((f: any) => f.id === folderId)).toBe(false);
        });
    });
});
