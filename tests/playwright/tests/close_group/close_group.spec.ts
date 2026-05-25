import { test, expect, type APIRequestContext } from '@playwright/test';
import { getUserContext, getAdminContext, expectCustomResponse, logRequestPayload, attachResponseToReport } from '../../utils/api-client';

test.describe('Close Group API', () => {
    let userContext: APIRequestContext;
    let closeGroupId: string;
    let memberId: string;
    const friendEmail = `friend_${Date.now()}@test.com`;

    test.beforeAll(async ({ baseURL }) => {
        userContext = await getUserContext();

        // Get the default close group (auto-created if needed)
        const cgListRes = await userContext.get(`${baseURL}/api/v1/close-group`);
        const cgListBody = await cgListRes.json();
        closeGroupId = (cgListBody.data ?? [])[0]?.id;

        // Clean up stale members from previous test runs
        if (closeGroupId) {
            const listRes = await userContext.get(`${baseURL}/api/v1/close-group/${closeGroupId}/members?page_size=100`);
            const listBody = await listRes.json();
            const existing = listBody.data?.results || listBody.data || [];
            for (const m of existing) {
                await userContext.delete(`${baseURL}/api/v1/close-group/${closeGroupId}/members/${m.id}`).catch(() => {});
            }
        }
    });

    test('User can list close groups', async ({ baseURL }) => {
        const response = await userContext.get(`${baseURL}/api/v1/close-group`);
        const body = await expectCustomResponse(response, 200, true, null, 'List Close Groups');
        expect(Array.isArray(body.data)).toBe(true);
        expect(body.data.length).toBeGreaterThan(0);
        expect(body.data[0]).toHaveProperty('id');
        expect(body.data[0]).toHaveProperty('name');
        expect(body.data[0]).toHaveProperty('member_count');
        closeGroupId = body.data[0].id;
    });

    test('User can get close group detail', async ({ baseURL }) => {
        expect(closeGroupId).toBeDefined();
        const response = await userContext.get(`${baseURL}/api/v1/close-group/${closeGroupId}`);
        const body = await expectCustomResponse(response, 200, true, null, 'Get Close Group Detail');
        expect(body.data.id).toBe(closeGroupId);
        expect(body.data).toHaveProperty('name');
        expect(body.data).toHaveProperty('member_count');
    });

    test('User can add a member to close group', async ({ baseURL }) => {
        expect(closeGroupId).toBeDefined();
        const requestPayload = { email: friendEmail };

        const response = await userContext.post(`${baseURL}/api/v1/close-group/${closeGroupId}/members`, {
            data: requestPayload
        });

        const body = await expectCustomResponse(response, 201, true, requestPayload, 'Add Close Group Member');
        expect(body.data).toHaveProperty('email');
        expect(body.data.email).toBe(friendEmail);
        expect(body.data).toHaveProperty('status');
        memberId = body.data.id;
    });

    test('User can list close group members', async ({ baseURL }) => {
        expect(closeGroupId).toBeDefined();
        const response = await userContext.get(`${baseURL}/api/v1/close-group/${closeGroupId}/members?page=1&page_size=10`);
        const body = await expectCustomResponse(response, 200, true, null, 'List Close Group Members');

        const results = body.data?.results || body.data;
        expect(Array.isArray(results)).toBe(true);
        const emails = results.map((m: any) => m.email);
        expect(emails).toContain(friendEmail);
    });

    test('User cannot add the same email twice', async ({ baseURL }) => {
        expect(closeGroupId).toBeDefined();
        const requestPayload = { email: friendEmail };

        await logRequestPayload('POST', `${baseURL}/api/v1/close-group/${closeGroupId}/members`, requestPayload, 'Add Duplicate Close Group Member');
        const response = await userContext.post(`${baseURL}/api/v1/close-group/${closeGroupId}/members`, {
            data: requestPayload
        });

        expect([400, 409]).toContain(response.status());
        const body = await response.json();
        await attachResponseToReport(body, 'Add Duplicate Close Group Member');
        expect(body.success).toBe(false);
    });

    test('Unauthenticated request is rejected', async ({ request, baseURL }) => {
        const testGroupId = closeGroupId || '00000000-0000-0000-0000-000000000000';
        await logRequestPayload('GET', `${baseURL}/api/v1/close-group/${testGroupId}/members`, null, 'List Close Group - Unauthenticated');
        const response = await request.get(`${baseURL}/api/v1/close-group/${testGroupId}/members`);

        expect([401, 403]).toContain(response.status());
        const body = await response.json().catch(() => ({}));
        await attachResponseToReport(body, 'List Close Group - Unauthenticated');
    });

    test('User can remove a member from close group', async ({ baseURL }) => {
        expect(memberId).toBeDefined();
        expect(closeGroupId).toBeDefined();

        await logRequestPayload('DELETE', `${baseURL}/api/v1/close-group/${closeGroupId}/members/${memberId}`, null, 'Remove Close Group Member');
        const response = await userContext.delete(`${baseURL}/api/v1/close-group/${closeGroupId}/members/${memberId}`);

        expect([200, 204]).toContain(response.status());
        const body = await response.json().catch(() => ({}));
        await attachResponseToReport(body, 'Remove Close Group Member');
        if ('success' in body) {
            expect(body.success).toBe(true);
        }
    });

    test('Removed member is no longer in close group list', async ({ baseURL }) => {
        expect(closeGroupId).toBeDefined();
        const response = await userContext.get(`${baseURL}/api/v1/close-group/${closeGroupId}/members?page=1&page_size=50`);
        const body = await expectCustomResponse(response, 200, true, null, 'List Close Group After Remove');

        const results = body.data?.results || body.data;
        const emails = (results as any[]).map((m: any) => m.email);
        expect(emails).not.toContain(friendEmail);
    });
});
