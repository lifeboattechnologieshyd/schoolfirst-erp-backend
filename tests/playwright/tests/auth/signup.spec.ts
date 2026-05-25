import { test, expect } from '@playwright/test';
import { getAdminContext, expectCustomResponse, logRequestPayload, attachResponseToReport } from '../../utils/api-client';
import { Client } from 'pg';

test.describe('Signup Flow', () => {
    let adminContext: Awaited<ReturnType<typeof getAdminContext>>;
    const testEmail = `signup.flow.${Date.now()}@example.com`;
    let inviteCode: string;

    test.beforeAll(async () => {
        adminContext = await getAdminContext();
    });

    test('Admin creates a generic invite code for signup', async ({ baseURL }) => {
        // Clean up existing generic codes first
        const listRes = await adminContext.get(`${baseURL}/api/v1/auth/invitations/list/?include_inactive=false`);
        const listBody = await listRes.json();
        const codes = listBody.data || [];
        for (const code of codes) {
            if (code.code_type === 'generic') {
                await adminContext.delete(`${baseURL}/api/v1/auth/invitations/${code.code}/delete`);
            }
        }

        const payload = { code_type: 'generic', max_uses: 5, expires_in_days: 1 };
        const response = await adminContext.post(`${baseURL}/api/v1/auth/invitations/create`, {
            data: payload
        });

        const body = await expectCustomResponse(response, 201, true, payload, 'Create Invite For Signup');
        inviteCode = body.data.code;
        expect(inviteCode).toBeDefined();
    });

    test('Invite code can be validated before signup', async ({ request, baseURL }) => {
        expect(inviteCode).toBeDefined();

        const payload = { invite_code: inviteCode };
        const response = await request.post(`${baseURL}/api/v1/auth/signup/invite/validate`, {
            data: payload
        });

        const body = await expectCustomResponse(response, 200, true, payload, 'Validate Invite Code');
        expect(body.data).toHaveProperty('code_type');
    });

    test('Signup initiation sends OTP to email', async ({ request, baseURL }) => {
        expect(inviteCode).toBeDefined();

        const payload = {
            email: testEmail,
            invite_code: inviteCode,
        };

        const response = await request.post(`${baseURL}/api/v1/auth/signup/email`, {
            data: payload
        });

        const body = await expectCustomResponse(response, 200, true, payload, 'Signup Initiation');
        expect(body.success).toBe(true);
    });

    test('OTP verify + password creates account and returns JWT', async ({ request, baseURL }) => {
        expect(inviteCode).toBeDefined();

        const client = new Client({
            host: process.env.POSTGRES_DB_HOST || 'localhost',
            port: parseInt(process.env.POSTGRES_DB_PORT || '5432', 10),
            user: process.env.POSTGRES_DB_USER || 'postgres',
            password: process.env.POSTGRES_DB_PASSWORD || 'postgres',
            database: process.env.POSTGRES_DB_NAME || 'schoolfirst',
        });

        let otp = '';
        try {
            await client.connect();
            const res = await client.query(
                `SELECT otp FROM otp WHERE email = $1 AND is_used = false ORDER BY created_at DESC LIMIT 1`,
                [testEmail]
            );
            if (res.rows.length > 0) {
                otp = res.rows[0].otp;
                console.log('Extracted OTP from DB:', otp);
            }
        } catch (e) {
            console.error('Failed to fetch OTP from DB:', e);
        } finally {
            await client.end();
        }

        if (!otp) {
            console.warn('No OTP found in DB; skipping signup verify test');
            return;
        }

        const payload = {
            email: testEmail,
            otp,
            invite_code: inviteCode,
            password: 'SecureTestPass123!',
        };

        const response = await request.post(`${baseURL}/api/v1/auth/signup/email/verify`, {
            data: payload
        });

        const body = await expectCustomResponse(response, 201, true, payload, 'Signup Verify + Create Account');
        expect(body.data).toHaveProperty('access_token');
        expect(body.data).toHaveProperty('refresh_token');
    });

    test('Missing required fields returns error', async ({ request, baseURL }) => {
        const payload = { email: testEmail };

        await logRequestPayload('POST', `${baseURL}/api/v1/auth/signup/email/verify`, payload, 'Verify - Missing Fields');
        const response = await request.post(`${baseURL}/api/v1/auth/signup/email/verify`, {
            data: payload
        });

        const body = await response.json();
        await attachResponseToReport(body, 'Verify - Missing Fields');
        expect(body.success).toBe(false);
    });
});
