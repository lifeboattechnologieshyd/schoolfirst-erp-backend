import { test, expect } from '@playwright/test';
import { getUserContext, expectCustomResponse, logRequestPayload, attachResponseToReport } from '../../utils/api-client';

test.describe('Profile API CRUD', () => {

    let userContext: Awaited<ReturnType<typeof getUserContext>>;

    test.beforeAll(async () => {
        userContext = await getUserContext();
    });

    test('User can get own profile', async ({ baseURL }) => {
        const response = await userContext.get(`${baseURL}/api/v1/user/profile`);
        const body = await expectCustomResponse(response, 200, true, null, 'Get Profile');

        expect(body.data).toHaveProperty('id');
        expect(body.data).toHaveProperty('email');
        expect(body.data).toHaveProperty('is_profile_updated');
    });

    test('User can update own profile', async ({ baseURL }) => {
        // Generate a random name to ensure update actually works
        const newName = `Test User ${Math.floor(Math.random() * 10000)}`;

        const requestPayload = {
            first_name: newName
        };

        const response = await userContext.patch(`${baseURL}/api/v1/user/profile`, {
            data: requestPayload
        });

        const body = await expectCustomResponse(response, 200, true, requestPayload, 'Update Profile');
        expect(body.data?.first_name).toBe(newName);
        expect(body.data?.is_profile_updated).toBe(true);
    });

    test('Unauthenticated user cannot get profile', async ({ request, baseURL }) => {
        await logRequestPayload('GET', `${baseURL}/api/v1/user/profile`, null, 'Unauthenticated Get Profile');
        const response = await request.get(`${baseURL}/api/v1/user/profile`);

        // Should be unauthorized
        expect([401, 403]).toContain(response.status());
        const body = await response.json().catch(() => ({}));
        await attachResponseToReport(body, 'Unauthenticated Get Profile');
    });

});
