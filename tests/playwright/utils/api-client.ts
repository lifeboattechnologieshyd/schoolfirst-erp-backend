import { request, type APIRequestContext, expect, test as baseTest } from '@playwright/test';

// Cache tokens to avoid logging in multiple times across tests
let adminToken: string | null = null;
let userToken: string | null = null;

export interface CustomResponse<T = any> {
    success: boolean;
    message?: string;
    data?: T;
    error?: any;
    meta?: any;
}

export async function loginAndGetToken(email?: string, password?: string): Promise<string> {
    const baseURL = process.env.BASE_URL || 'http://localhost:8000';

    if (!email || !password) {
        throw new Error('Email or password not provided.');
    }

    const context = await request.newContext({ baseURL });

    const response = await context.post('/api/v1/auth/login', {
        data: { email, password },
    });

    const body = await response.json() as CustomResponse;

    if (!response.ok() || !body.success) {
        console.error(`Login failed for ${email}:`, body);
        throw new Error(`Failed to login: ${JSON.stringify(body.error)}`);
    }

    const token = body.data?.access_token || body.data?.tokens?.access || body.data?.access;
    if (!token) {
        throw new Error(`Token not found in response for ${email}`);
    }

    return token;
}

export async function getAdminContext(): Promise<APIRequestContext> {
    if (!adminToken) {
        adminToken = await loginAndGetToken(
            process.env.TEST_ADMIN_EMAIL,
            process.env.TEST_ADMIN_PASSWORD
        );
    }

    return request.newContext({
        baseURL: process.env.BASE_URL || 'http://localhost:8000',
        extraHTTPHeaders: {
            'Authorization': `Bearer ${adminToken}`,
            'Accept': 'application/json',
        },
    });
}

export async function getUserContext(): Promise<APIRequestContext> {
    if (!userToken) {
        userToken = await loginAndGetToken(
            process.env.TEST_USER_EMAIL,
            process.env.TEST_USER_PASSWORD
        );
    }

    return request.newContext({
        baseURL: process.env.BASE_URL || 'http://localhost:8000',
        extraHTTPHeaders: {
            'Authorization': `Bearer ${userToken}`,
            'Accept': 'application/json',
        },
    });
}

// Helper to attach a pre-parsed response body to the HTML report
export async function attachResponseToReport(body: any, description?: string) {
    const attachmentName = description ? `📡 Response (${description})` : '📡 Response';
    await baseTest.info().attach(attachmentName, {
        body: JSON.stringify(body, null, 2),
        contentType: 'application/json'
    });
    console.log(`\n${attachmentName}:`, JSON.stringify(body, null, 2));
}

// Helper to log request payload
export async function logRequestPayload(method: string, url: string, payload?: any, description?: string) {
    const requestInfo = {
        method,
        url,
        payload: payload || null
    };

    const attachmentName = description ? `📤 Request (${description})` : '📤 Request';
    await baseTest.info().attach(attachmentName, {
        body: JSON.stringify(requestInfo, null, 2),
        contentType: 'application/json'
    });

    console.log(`\n${attachmentName}:`, JSON.stringify(requestInfo, null, 2));
}

// Helper generic custom assertion to ensure endpoints follow the uniform response structure
export async function expectCustomResponse(
    response: any,
    expectedStatus = 200,
    isSuccess = true,
    requestPayload?: any,
    description?: string
) {
    // Log request payload if provided
    if (requestPayload !== undefined) {
        await logRequestPayload('REQUEST', response.url(), requestPayload, description);
    }

    const body = await response.json();

    // Automatically attach the API response for visibility in HTML report
    const attachmentName = description ? `📡 Response (${description})` : '📡 Response';
    await baseTest.info().attach(attachmentName, {
        body: JSON.stringify(body, null, 2),
        contentType: 'application/json'
    });

    // Also log to console for terminal visibility
    console.log(`\n${attachmentName}:`, JSON.stringify(body, null, 2));

    expect(response.status()).toBe(expectedStatus);
    expect(body).toHaveProperty('success', isSuccess);
    if (isSuccess) {
        expect(body).toHaveProperty('data');
    } else {
        expect(body).toHaveProperty('error');
        expect(body.error).toHaveProperty('code');
    }

    return body;
}
