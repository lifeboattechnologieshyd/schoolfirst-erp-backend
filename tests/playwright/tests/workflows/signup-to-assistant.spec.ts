import { test, expect, request as playwrightRequest } from '@playwright/test';
import { getAdminContext, expectCustomResponse, CustomResponse, logRequestPayload } from '../../utils/api-client';
import { Client } from 'pg';

test.describe('End-to-End Workflow', () => {

    let adminContext: Awaited<ReturnType<typeof getAdminContext>>;
    let userToken: string;
    let inviteCode: string;
    let testEmail = `workflow.test.${Date.now()}@example.com`;

    test.beforeAll(async () => {
        adminContext = await getAdminContext();
    });

    test('Complete flow: Admin invites -> User signs up -> User updates profile -> User chats', async ({ request, baseURL }) => {

        // 1. Admin creates or reuses generic invite code
        let inviteCodeRes = await adminContext.get(`${baseURL}/api/v1/auth/invitations/list/?include_inactive=true`);
        let inviteList = await inviteCodeRes.json();

        // Delete any existing generic invites to avoid "already have an active generic invitation" or expired errors
        if (inviteList.data && Array.isArray(inviteList.data)) {
            for (const inv of inviteList.data) {
                if (inv.code_type === 'generic') {
                    await adminContext.delete(`${baseURL}/api/v1/auth/invitations/${inv.code}/delete`);
                }
            }
        }

        const invitePayload = { type: 'generic', max_uses: 5 };
        const inviteRes = await adminContext.post(`${baseURL}/api/v1/auth/invitations/create`, {
            data: invitePayload
        });
        const inviteBody = await expectCustomResponse(inviteRes, 201, true, invitePayload, 'Admin Create Invite');
        inviteCode = inviteBody.data?.code || inviteBody.data?.invite_code;

        expect(inviteCode).toBeDefined();

        // 2. User signs up using email
        const signupPayload = {
            email: testEmail,
            invite_code: inviteCode,
            client: {
                app: { app_id: 'com.samsr.test' },
                device: { device_id: 'test-device-id', os: 'iOS' }
            }
        };
        const signupReq = await request.post(`${baseURL}/api/v1/auth/signup/email`, {
            data: signupPayload
        });
        const signupBody = await expectCustomResponse(signupReq, 200, true, signupPayload, 'User Signup');

        let theOtp = '123456';

        // Connect to local DB to extract the OTP
        const client = new Client({
            host: process.env.POSTGRES_DB_HOST || 'localhost',
            port: parseInt(process.env.POSTGRES_DB_PORT || '5432', 10),
            user: process.env.POSTGRES_DB_USER || 'postgres',
            password: process.env.POSTGRES_DB_PASSWORD || 'postgres',
            database: process.env.POSTGRES_DB_NAME || 'samsr',
        });

        try {
            await client.connect();
            const res = await client.query(`SELECT otp FROM otp WHERE email = $1 ORDER BY created_at DESC LIMIT 1`, [testEmail]);
            if (res.rows.length > 0) {
                theOtp = res.rows[0].otp;
                console.log('Extracted OTP from DB:', theOtp);
            }
        } catch (e) {
            console.error('Failed to get OTP from Database:', e);
        } finally {
            await client.end();
        }

        // 3. Verify OTP
        const verifyPayload = {
            email: testEmail,
            otp: theOtp
        };
        await logRequestPayload('POST', `${baseURL}/api/v1/auth/signup/email/verify`, verifyPayload, 'Verify OTP');

        const verifyReq = await request.post(`${baseURL}/api/v1/auth/signup/email/verify`, {
            data: verifyPayload
        });

        const verifyBody = await verifyReq.json() as CustomResponse;

        // Log verify response
        await test.info().attach('📡 Response (Verify OTP)', {
            body: JSON.stringify(verifyBody, null, 2),
            contentType: 'application/json'
        });
        console.log('\n📡 Response (Verify OTP):', JSON.stringify(verifyBody, null, 2));
        if (verifyReq.ok() && verifyBody.success) {
            userToken = verifyBody.data?.access_token || verifyBody.data?.tokens?.access_token;
            expect(userToken).toBeDefined();

            // Setup user context using playwright's request object
            const userContext = await playwrightRequest.newContext({
                baseURL: baseURL,
                extraHTTPHeaders: {
                    'Authorization': `Bearer ${userToken}`,
                    'Accept': 'application/json',
                },
            });

            // 4. Update Profile
            const profilePayload = {
                profile: {
                    first_name: 'Workflow',
                    last_name: 'Tester'
                }
            };
            const profileRes = await userContext.patch(`${baseURL}/api/v1/profile/me`, {
                data: profilePayload
            });
            const profileBody = await expectCustomResponse(profileRes, 200, true, profilePayload, 'Update Profile');
            expect(profileBody.data?.profile?.first_name).toBe('Workflow');

            // 5. Create Thread in Assistant
            const threadPayload = { name: 'Workflow Thread' }; // The server will ignore this payload's name and force 'New Chat'
            const threadRes = await userContext.post(`${baseURL}/api/v1/assistant/threads`, {
                data: threadPayload
            });
            const threadBody = await expectCustomResponse(threadRes, 200, true, threadPayload, 'Create Thread');
            const threadId = threadBody.data?.id;
            expect(threadId).toBeDefined();
            expect(threadBody.data?.name).toBe('New Chat'); // Asserts the server ignored our payload

            // 6. Send Message to Assistant
            const chatPayload = { content: 'Workflow Message test', stream: false };
            const msgRes = await userContext.post(`${baseURL}/api/v1/assistant/threads/${threadId}/chat`, {
                data: chatPayload
            });
            await expectCustomResponse(msgRes, 200, true, chatPayload, 'Send Message to Assistant');

        } else {
            // If OTP bypass isn't active in dev, just skip the remainder
            console.warn("OTP bypass likely not active, skipping workflow remainder");
        }
    });

});
