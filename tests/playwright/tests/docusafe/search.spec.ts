import { test, expect, type APIRequestContext } from '@playwright/test';
import { getUserContext, getAdminContext, expectCustomResponse } from '../../utils/api-client.js';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test.describe('Docusafe Vector Search API', () => {
    let ownerContext: APIRequestContext;
    let guestContext: APIRequestContext;
    let folderId: string;
    let guestFolderId: string;

    test.beforeAll(async () => {
        ownerContext = await getUserContext();
        guestContext = await getAdminContext();

        // Create a test folder for search tests
        const folderPayload = {
            name: `Search Test Folder ${Date.now()}`,
            description: 'Folder for vector search testing'
        };
        const folderRes = await ownerContext.post('/api/v1/docusafe/folders', { data: folderPayload });
        const folderBody = await folderRes.json();
        folderId = folderBody.data.id;

        const guestFolderRes = await guestContext.post('/api/v1/docusafe/folders', {
            data: {
                name: `Guest Search Folder ${Date.now()}`,
                description: 'Folder owned by a different user for search access checks'
            }
        });
        const guestFolderBody = await guestFolderRes.json();
        guestFolderId = guestFolderBody.data.id;
    });

    test.afterAll(async () => {
        // Cleanup: Delete test folder
        if (folderId) {
            await ownerContext.delete(`/api/v1/docusafe/folders/${folderId}`);
        }
        if (guestFolderId) {
            await guestContext.delete(`/api/v1/docusafe/folders/${guestFolderId}`);
        }
    });

    test('Search endpoint validation and response structure', async () => {
        // 1. Missing query — should fail validation
        await test.step('Search with empty body should fail', async () => {
            const res = await ownerContext.post('/api/v1/docusafe/search', {
                data: {}
            });
            expect(res.status()).toBe(400);
        });

        // 2. Valid query — should return proper response structure (even with no matching vectors)
        await test.step('Search with valid query returns proper structure', async () => {
            const searchPayload = { query: 'test document content', limit: 5 };
            const res = await ownerContext.post('/api/v1/docusafe/search', {
                data: searchPayload
            });

            const body = await res.json();

            // Attach for test report
            await test.info().attach('📡 Search Response', {
                body: JSON.stringify(body, null, 2),
                contentType: 'application/json'
            });

            expect(res.status()).toBe(200);
            expect(body.success).toBe(true);
            expect(body).toHaveProperty('data');
            expect(Array.isArray(body.data)).toBe(true);
            expect(body).toHaveProperty('message');
        });

        // 3. Search with folder_id filter
        await test.step('Search with folder filter returns proper structure', async () => {
            const searchPayload = {
                query: 'invoice',
                folder_id: folderId,
                limit: 10
            };
            const res = await ownerContext.post('/api/v1/docusafe/search', {
                data: searchPayload
            });

            const body = await res.json();

            await test.info().attach('📡 Search with folder filter', {
                body: JSON.stringify(body, null, 2),
                contentType: 'application/json'
            });

            expect(res.status()).toBe(200);
            expect(body.success).toBe(true);
            expect(Array.isArray(body.data)).toBe(true);
        });

        // 4. Search with invalid limit
        await test.step('Search with limit > 50 should fail', async () => {
            const res = await ownerContext.post('/api/v1/docusafe/search', {
                data: { query: 'test', limit: 100 }
            });
            expect(res.status()).toBe(400);
        });

        // 5. Search with limit = 0
        await test.step('Search with limit < 1 should fail', async () => {
            const res = await ownerContext.post('/api/v1/docusafe/search', {
                data: { query: 'test', limit: 0 }
            });
            expect(res.status()).toBe(400);
        });

        // 6. Search requires authentication
        await test.step('Search without auth should fail', async () => {
            const { request } = await import('@playwright/test');
            const anonContext = await request.newContext({
                baseURL: process.env.BASE_URL || 'http://localhost:8000',
            });
            const res = await anonContext.post('/api/v1/docusafe/search', {
                data: { query: 'test' }
            });
            expect(res.status()).toBe(401);
            await anonContext.dispose();
        });

        // 7. Query too long
        await test.step('Search with query > 1000 chars should fail', async () => {
            const longQuery = 'a'.repeat(1001);
            const res = await ownerContext.post('/api/v1/docusafe/search', {
                data: { query: longQuery }
            });
            expect(res.status()).toBe(400);
        });

        // 8. Search with folder_id owned by another user
        await test.step('Search with unowned folder filter should return validation error', async () => {
            const res = await ownerContext.post('/api/v1/docusafe/search', {
                data: { query: 'policy', folder_id: guestFolderId }
            });
            const body = await res.json();

            await test.info().attach('📡 Search with unowned folder filter', {
                body: JSON.stringify(body, null, 2),
                contentType: 'application/json'
            });

            expect(res.status()).toBe(400);
            expect(body.success).toBe(false);
            expect(body.error.message).toContain('validation error');
            expect(body.error.details[0].message).toContain('Folder not found or you do not have access.');
        });
    });

    test('File upload sets llm_status to PENDING for embeddable files', async () => {
        // Upload a text file (embeddable)
        await test.step('Upload .txt file — llm_status should be PENDING', async () => {
            const tempPath = path.join(__dirname, 'test-embed-check.txt');
            fs.writeFileSync(tempPath, 'This is a test document for embedding verification.');

            const uploadRes = await ownerContext.post(`/api/v1/docusafe/folders/${folderId}/files`, {
                multipart: {
                    file: {
                        name: 'embed-check.txt',
                        mimeType: 'text/plain',
                        buffer: fs.readFileSync(tempPath),
                    },
                    file_name: 'embed-check.txt',
                    description: 'File for embedding status verification'
                }
            });
            const body = await expectCustomResponse(uploadRes, 201, true, null, 'Upload for embedding check');

            expect(body.data.llm_status).toBe('PENDING');
            expect(body.data.file_extension).toBe('.txt');

            // Verify file detail also shows llm_status
            const detailRes = await ownerContext.get(`/api/v1/docusafe/folders/${folderId}/files/${body.data.id}`);
            const detailBody = await detailRes.json();
            expect(detailBody.data.llm_status).toBe('PENDING');

            fs.unlinkSync(tempPath);
        });

        // Upload an image file (not embeddable currently — only documents)
        await test.step('Upload .png file — llm_status should be PENDING (processed by cron)', async () => {
            const tempPath = path.join(__dirname, 'test-nonembed.png');
            // Create a minimal valid PNG (1x1 pixel)
            const pngBuffer = Buffer.from([
                0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, // PNG signature
                0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52, // IHDR chunk
                0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
                0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
                0xde, 0x00, 0x00, 0x00, 0x0c, 0x49, 0x44, 0x41, // IDAT chunk
                0x54, 0x08, 0xd7, 0x63, 0xf8, 0xcf, 0xc0, 0x00,
                0x00, 0x00, 0x02, 0x00, 0x01, 0xe2, 0x21, 0xbc,
                0x33, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4e, // IEND chunk
                0x44, 0xae, 0x42, 0x60, 0x82
            ]);
            fs.writeFileSync(tempPath, pngBuffer);

            const uploadRes = await ownerContext.post(`/api/v1/docusafe/folders/${folderId}/files`, {
                multipart: {
                    file: {
                        name: 'nonembed.png',
                        mimeType: 'image/png',
                        buffer: pngBuffer,
                    },
                    file_name: 'nonembed.png',
                    description: 'Image file - not embeddable'
                }
            });
            const body = await expectCustomResponse(uploadRes, 201, true, null, 'Upload non-embeddable file');

            // llm_status starts as PENDING — cron will mark it NOT_SUPPORTED
            expect(body.data.llm_status).toBe('PENDING');

            fs.unlinkSync(tempPath);
        });
    });

    test('Search results format validation', async () => {
        // Upload a file and verify search response format
        await test.step('Verify search result schema when results exist', async () => {
            // Even if there are no matching vectors, we verify the endpoint
            // returns the proper response envelope
            const searchPayload = { query: 'embed-check.txt', limit: 10 };
            const res = await ownerContext.post('/api/v1/docusafe/search', {
                data: searchPayload
            });

            const body = await res.json();

            await test.info().attach('📡 Search Results', {
                body: JSON.stringify(body, null, 2),
                contentType: 'application/json'
            });

            expect(res.status()).toBe(200);
            expect(body.success).toBe(true);
            expect(Array.isArray(body.data)).toBe(true);

            // If results exist (e.g., from prior process_embeddings run), validate schema
            if (body.data.length > 0) {
                const result = body.data[0];
                expect(result).toHaveProperty('file_id');
                expect(result).toHaveProperty('file_name');
                expect(result).toHaveProperty('folder_id');
                expect(result).toHaveProperty('score');
                expect(result).toHaveProperty('match_type');
                expect(result).not.toHaveProperty('snippet');
                expect(result).toHaveProperty('file_extension');
                expect(result).toHaveProperty('mime_type');
                expect(result).toHaveProperty('file_size');

                // Validate match_type is one of the expected values
                expect(['CHUNK', 'TITLE', 'SUMMARY']).toContain(result.match_type);

                // Score should be a positive number
                expect(result.score).toBeGreaterThanOrEqual(0);
            }
        });
    });

    test('Cross-user search isolation', async () => {
        // Verify that guest user cannot see owner's files via search
        await test.step('Guest search should not return owner files', async () => {
            const searchPayload = { query: 'embed-check', limit: 10 };
            const res = await guestContext.post('/api/v1/docusafe/search', {
                data: searchPayload
            });

            const body = await res.json();

            await test.info().attach('📡 Guest Search Response', {
                body: JSON.stringify(body, null, 2),
                contentType: 'application/json'
            });

            expect(res.status()).toBe(200);
            expect(body.success).toBe(true);
            // Guest should never see owner's files (search filters by user_id)
            expect(Array.isArray(body.data)).toBe(true);

            // If any results came back, none should belong to the owner's folder
            for (const result of body.data) {
                expect(result.folder_id).not.toBe(folderId);
            }
        });
    });
});
