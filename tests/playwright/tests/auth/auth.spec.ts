import { test, expect } from '@playwright/test';
import { getAdminContext, getUserContext, expectCustomResponse } from '../../utils/api-client';

test.describe('Auth API CRUD & Workflows', () => {

    test('User can login via email', async ({ request, baseURL }) => {
        const requestPayload = {
            email: process.env.TEST_USER_EMAIL,
            password: process.env.TEST_USER_PASSWORD,
        };

        const response = await request.post(`${baseURL}/api/v1/auth/login`, {
            data: requestPayload
        });

        const body = await expectCustomResponse(response, 200, true, requestPayload, 'User Login');

        expect(body.data).toHaveProperty('access_token');
        expect(body.data).toHaveProperty('refresh_token');
        expect(body.data).toHaveProperty('user');
        expect(body.data.user).toHaveProperty('id');
        expect(body.data.user).toHaveProperty('email');
        expect(body.data.user).toHaveProperty('is_profile_updated');
        expect(body.data.user).toHaveProperty('is_password_updated');
    });

    test('Fails on invalid login', async ({ request, baseURL }) => {
        const requestPayload = {
            email: 'invalid@example.com',
            password: 'wrongpassword',
        };

        const response = await request.post(`${baseURL}/api/v1/auth/login`, {
            data: requestPayload
        });

        // The API returns HTTP 200 but sets success=false inside the custom wrapper
        const body = await expectCustomResponse(response, 200, false, requestPayload, 'Invalid Login');

        expect(body.error.code).toBeDefined();
    });

    test('Fails on missing body fields in login', async ({ request, baseURL }) => {
        const requestPayload = { email: process.env.TEST_USER_EMAIL }; // Missing password

        const response = await request.post(`${baseURL}/api/v1/auth/login`, {
            data: requestPayload
        });

        // The API returns HTTP 200 but sets success=false for validation errors
        const body = await expectCustomResponse(response, 200, false, requestPayload, 'Missing Password');

        expect(body.error.code).toBeDefined();
        expect(body.error.message).toBeDefined();
    });

    test('User can refresh access token', async ({ request, baseURL }) => {
        const loginRes = await request.post(`${baseURL}/api/v1/auth/login`, {
            data: {
                email: process.env.TEST_USER_EMAIL,
                password: process.env.TEST_USER_PASSWORD,
            }
        });

        const loginBody = await loginRes.json();
        const refreshToken = loginBody.data?.refresh_token;

        expect(refreshToken).toBeDefined();

        const requestPayload = { refresh_token: refreshToken };

        const response = await request.post(`${baseURL}/api/v1/auth/refresh`, {
            data: requestPayload
        });

        const body = await expectCustomResponse(response, 200, true, requestPayload, 'Refresh Token');
        expect(body.data).toBeDefined();
    });

});
