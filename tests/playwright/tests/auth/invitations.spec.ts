import { test, expect } from '@playwright/test';
import { getAdminContext, getUserContext, expectCustomResponse, logRequestPayload, attachResponseToReport } from '../../utils/api-client';

test.describe('Invitations API CRUD', () => {

    let adminContext: Awaited<ReturnType<typeof getAdminContext>>;
    let createdInviteCode: string;

    test.beforeAll(async () => {
        adminContext = await getAdminContext();
    });

    test('Admin can create generic invite code', async ({ baseURL }) => {
        // First delete any existing active generic codes to avoid constraints
        const listRes = await adminContext.get(`${baseURL}/api/v1/auth/invitations/list/?include_inactive=true`);
        const listBody = await expectCustomResponse(listRes, 200, true, null, 'List Existing Invite Codes');
        const invites = listBody.data.results || listBody.data;
        for (const invite of invites) {
            if (invite.code_type === 'generic') {
                await adminContext.delete(`${baseURL}/api/v1/auth/invitations/${invite.code}/delete`);
            }
        }

        const requestPayload = {
            code_type: 'generic',
            max_uses: 10
        };

        await logRequestPayload('POST', `${baseURL}/api/v1/auth/invitations/create`, requestPayload, 'Create Generic Invite Code');
        const response = await adminContext.post(`${baseURL}/api/v1/auth/invitations/create`, {
            data: requestPayload
        });

        expect([200, 201]).toContain(response.status());
        const body = await response.json();
        await attachResponseToReport(body, 'Create Generic Invite Code');
        expect(body.success).toBeTruthy();
        expect(body.data).toHaveProperty('code');

        createdInviteCode = body.data.code;
    });

    test('Admin can list invite codes', async ({ baseURL }) => {
        const response = await adminContext.get(`${baseURL}/api/v1/auth/invitations/list`);
        const body = await expectCustomResponse(response, 200, true, null, 'Admin List Invites');

        expect(Array.isArray(body.data.results || body.data)).toBeTruthy();
    });

    test('User can validate invite code', async ({ request, baseURL }) => {
        expect(createdInviteCode).toBeDefined();

        const requestPayload = {
            invite_code: createdInviteCode
        };

        const response = await request.post(`${baseURL}/api/v1/auth/signup/invite/validate`, {
            data: requestPayload
        });

        const body = await expectCustomResponse(response, 200, true, requestPayload, 'Validate Invite Code');
        expect(body.data).toBeDefined();
    });

    test('Fails to validate invalid invite code', async ({ request, baseURL }) => {
        const requestPayload = {
            invite_code: 'INVALID_CODE_123'
        };

        const response = await request.post(`${baseURL}/api/v1/auth/signup/invite/validate`, {
            data: requestPayload
        });

        await expectCustomResponse(response, 400, false, requestPayload, 'Invalid Invite Code');
    });

    test('Admin can get users who used an invite code', async ({ baseURL }) => {
        expect(createdInviteCode).toBeDefined();

        const response = await adminContext.get(
            `${baseURL}/api/v1/auth/invitations/${createdInviteCode}/users`
        );

        const body = await expectCustomResponse(response, 200, true, null, 'Get Invite Code Users');
        expect(body.data).toHaveProperty('invite_code');
        expect(body.data).toHaveProperty('users');
        expect(body.data).toHaveProperty('total');
        expect(Array.isArray(body.data.users)).toBe(true);
    });

    test('Admin can delete invite code', async ({ baseURL }) => {
        expect(createdInviteCode).toBeDefined();

        await logRequestPayload('DELETE', `${baseURL}/api/v1/auth/invitations/${createdInviteCode}/delete`, null, 'Delete Invite Code');
        const response = await adminContext.delete(`${baseURL}/api/v1/auth/invitations/${createdInviteCode}/delete`);

        expect([200, 204]).toContain(response.status());
        const body = await response.json();
        await attachResponseToReport(body, 'Delete Invite Code');
        expect(body.success).toBeTruthy();
    });

});
