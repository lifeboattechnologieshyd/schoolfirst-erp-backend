import { test, expect } from '@playwright/test';
import { expectCustomResponse, logRequestPayload, attachResponseToReport } from '../../utils/api-client';

test.describe('Membership Application API', () => {
    const applicantEmail = `membership.test.${Date.now()}@example.com`;

    test('Anyone can apply for membership', async ({ request, baseURL }) => {
        const requestPayload = {
            name: 'Test User',
            email: applicantEmail,
            mobile: '+919876543210',
            source: 'Youtube',
            remarks: 'I have read about SamsR through youtube video, it\'s very great and I want to Join the club'
        };

        const response = await request.post(`${baseURL}/api/v1/membership/apply`, {
            data: requestPayload
        });

        const body = await expectCustomResponse(response, 201, true, requestPayload, 'Apply For Membership');
        expect(body.success).toBe(true);
    });

    test('Cannot apply twice with same email', async ({ request, baseURL }) => {
        const requestPayload = {
            name: 'Test User',
            email: applicantEmail,
            remarks: 'Duplicate attempt'
        };

        await logRequestPayload('POST', `${baseURL}/api/v1/membership/apply`, requestPayload, 'Apply Membership - Duplicate Email');
        const response = await request.post(`${baseURL}/api/v1/membership/apply`, {
            data: requestPayload
        });

        const body = await response.json();
        await attachResponseToReport(body, 'Apply Membership - Duplicate Email');
        expect(body.success).toBe(false);
    });

    test('Missing email returns error when applying', async ({ request, baseURL }) => {
        const requestPayload = { name: 'No Email', remarks: 'No email provided' };

        await logRequestPayload('POST', `${baseURL}/api/v1/membership/apply`, requestPayload, 'Apply Membership - Missing Email');
        const response = await request.post(`${baseURL}/api/v1/membership/apply`, {
            data: requestPayload
        });

        const body = await response.json();
        await attachResponseToReport(body, 'Apply Membership - Missing Email');
        expect(body.success).toBe(false);
    });

    test('Missing name returns error when applying', async ({ request, baseURL }) => {
        const requestPayload = { email: `no.name.${Date.now()}@example.com`, remarks: 'No name provided' };

        await logRequestPayload('POST', `${baseURL}/api/v1/membership/apply`, requestPayload, 'Apply Membership - Missing Name');
        const response = await request.post(`${baseURL}/api/v1/membership/apply`, {
            data: requestPayload
        });

        const body = await response.json();
        await attachResponseToReport(body, 'Apply Membership - Missing Name');
        expect(body.success).toBe(false);
    });
});
