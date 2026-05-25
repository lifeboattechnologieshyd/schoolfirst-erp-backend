import { test, expect } from '@playwright/test';
import { getUserContext, expectCustomResponse } from '../../utils/api-client';
import "fs";

test.describe('Upload API', () => {

    let userContext: Awaited<ReturnType<typeof getUserContext>>;

    test.beforeAll(async () => {
        userContext = await getUserContext();
    });

    test('User can upload a file', async ({ baseURL }) => {
        const buffer = Buffer.from('this is a test file for upload');

        const multipartData = {
            file: {
                name: 'test.txt',
                mimeType: 'text/plain',
                buffer: buffer,
            },
            // Provide standard fields if your upload endpoint requires them
            // type: 'avatar'
        };

        const response = await userContext.post(`${baseURL}/api/v1/upload`, {
            multipart: multipartData
        });

        const body = await expectCustomResponse(response, 201, true, { file: 'test.txt (text/plain)' }, 'Upload File');
        expect(body.data).toHaveProperty('path');
    });

    test('Fails on missing file', async ({ baseURL }) => {
        const multipartData = {
            dummy_field: 'just to make it multipart'
        };

        const response = await userContext.post(`${baseURL}/api/v1/upload`, {
            multipart: multipartData
        });

        await expectCustomResponse(response, 400, false, multipartData, 'Missing File');
    });

});
