import { test, expect } from '@playwright/test';
import { getUserContext, getAdminContext, expectCustomResponse, logRequestPayload, attachResponseToReport } from '../../utils/api-client';

test.describe('User Lookup API', () => {
    let userContext: Awaited<ReturnType<typeof getUserContext>>;
    let adminContext: Awaited<ReturnType<typeof getAdminContext>>;

    test.beforeAll(async () => {
        userContext = await getUserContext();
        adminContext = await getAdminContext();
    });

    test('Authenticated user can look up an existing user by email', async ({ baseURL }) => {
        const requestPayload = { email: process.env.TEST_ADMIN_EMAIL! };

        const response = await userContext.post(`${baseURL}/api/v1/users/lookup`, {
            data: requestPayload
        });

        const body = await expectCustomResponse(response, 200, true, requestPayload, 'User Lookup - Found');
        expect(body.data).toBeDefined();
        expect(body.data).toHaveProperty('gender');
    });

    test('Returns not found for non-existent email', async ({ baseURL }) => {
        const requestPayload = { email: `nonexistent.${Date.now()}@example.com` };

        await logRequestPayload('POST', `${baseURL}/api/v1/users/lookup`, requestPayload, 'User Lookup - Not Found');
        const response = await userContext.post(`${baseURL}/api/v1/users/lookup`, {
            data: requestPayload
        });

        expect(response.status()).toBe(404);
        const body = await response.json();
        await attachResponseToReport(body, 'User Lookup - Not Found');
        expect(body.success).toBe(false);
        expect(body.error).toBeDefined();
    });

    test('Unauthenticated request is rejected', async ({ request, baseURL }) => {
        const requestPayload = { email: process.env.TEST_ADMIN_EMAIL! };

        await logRequestPayload('POST', `${baseURL}/api/v1/users/lookup`, requestPayload, 'User Lookup - Unauthenticated');
        const response = await request.post(`${baseURL}/api/v1/users/lookup`, {
            data: requestPayload
        });

        expect([401, 403]).toContain(response.status());
        const body = await response.json().catch(() => ({}));
        await attachResponseToReport(body, 'User Lookup - Unauthenticated');
    });

    test('Missing email returns validation error', async ({ baseURL }) => {
        const requestPayload = {};

        await logRequestPayload('POST', `${baseURL}/api/v1/users/lookup`, requestPayload, 'User Lookup - Missing Email');
        const response = await userContext.post(`${baseURL}/api/v1/users/lookup`, {
            data: requestPayload
        });

        expect(response.status()).toBe(400);
        const body = await response.json();
        await attachResponseToReport(body, 'User Lookup - Missing Email');
        // DRF returns raw validation errors here (no custom exception handler)
        expect(body.email || body.success === false || body.error).toBeTruthy();
    });
});
