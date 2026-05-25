import { test, expect } from '@playwright/test';
import { randomUUID } from 'crypto';
import { getUserContext, getAdminContext, expectCustomResponse, logRequestPayload, attachResponseToReport } from '../../utils/api-client';

// Module-scope state — set in beforeAll so it survives any Playwright worker restart
let ownerContext: Awaited<ReturnType<typeof getUserContext>>;
let memberContext: Awaited<ReturnType<typeof getAdminContext>>;
let familyId: string;
let deletedFamilyId: string;
let familyMemberId: string;
let pendingInviteEmail: string;
let pendingInviteMemberId: string;

const ignoredExistingUserProfile = {
    first_name: '__IGNORED_FIRST__',
    last_name: '__IGNORED_LAST__',
    gender: '__IGNORED_GENDER__',
};

const pendingInviteProfile = {
    first_name: 'Asha',
    last_name: 'Rao',
    gender: 'female',
};

test.describe('Family API', () => {

    test.beforeAll(async ({ baseURL }) => {
        ownerContext = await getUserContext();
        memberContext = await getAdminContext();

        // Clean up any family already owned by TEST_USER to start fresh
        const listRes = await ownerContext.get(`${baseURL}/api/v1/family`);
        const listBody = await listRes.json();
        for (const fam of (listBody.data || [])) {
            if (fam.is_owner) {
                await ownerContext.delete(`${baseURL}/api/v1/family/${fam.id}`);
            }
        }

        // Create the test family
        const createRes = await ownerContext.post(`${baseURL}/api/v1/family`, {
            data: { name: 'Test Family' },
        });
        const createBody = await createRes.json();
        familyId = createBody.data.id;
        pendingInviteEmail = `pending.family.${randomUUID()}@example.com`;

        // Add admin as an invited member
        const addRes = await ownerContext.post(`${baseURL}/api/v1/family/${familyId}/members`, {
            data: {
                email: process.env.TEST_ADMIN_EMAIL!,
                relation: 'friend',
                ...ignoredExistingUserProfile,
            },
        });
        const addBody = await addRes.json();
        familyMemberId = addBody.data.id;

        const addPendingInviteRes = await ownerContext.post(`${baseURL}/api/v1/family/${familyId}/members`, {
            data: {
                email: pendingInviteEmail,
                relation: 'cousin',
                ...pendingInviteProfile,
            },
        });
        const addPendingInviteBody = await addPendingInviteRes.json();
        pendingInviteMemberId = addPendingInviteBody.data.id;
    });

    test.afterAll(async ({ baseURL }) => {
        // Clean up if the delete-family test didn't run or failed
        if (familyId && ownerContext) {
            await ownerContext.delete(`${baseURL}/api/v1/family/${familyId}`).catch(() => {});
        }
    });

    // ── Create / constraint ──────────────────────────────────────────────────

    test('Owner cannot create a second family (one-per-user constraint)', async ({ baseURL }) => {
        const payload = { name: 'Another Family' };
        const response = await ownerContext.post(`${baseURL}/api/v1/family`, { data: payload });
        const body = await expectCustomResponse(response, 400, false, payload, 'Create Second Family');
        expect(body.error).toBeDefined();
    });

    // ── List / detail ────────────────────────────────────────────────────────

    test('Owner list includes owned family with is_owner=true and user_status=joined', async ({ baseURL }) => {
        const response = await ownerContext.get(`${baseURL}/api/v1/family`);
        const body = await expectCustomResponse(response, 200, true, null, 'List Families');

        const families: any[] = body.data;
        expect(Array.isArray(families)).toBe(true);

        const owned = families.find((f: any) => f.id === familyId);
        expect(owned).toBeDefined();
        expect(owned.is_owner).toBe(true);
        expect(owned.name).toBe('Test Family');
        expect(owned.user_status).toBe('joined');
    });

    test('Owner can get family detail with members array', async ({ baseURL }) => {
        const response = await ownerContext.get(`${baseURL}/api/v1/family/${familyId}`);
        const body = await expectCustomResponse(response, 200, true, null, 'Get Family Detail');

        expect(body.data.id).toBe(familyId);
        expect(body.data.is_owner).toBe(true);
        expect(body.data).toHaveProperty('members');
        expect(Array.isArray(body.data.members)).toBe(true);

        const pendingInvite = body.data.members.find((member: any) => member.id === pendingInviteMemberId);
        expect(pendingInvite).toBeDefined();
        expect(pendingInvite.user).toBeNull();
        expect(pendingInvite.first_name).toBe(pendingInviteProfile.first_name);
        expect(pendingInvite.last_name).toBe(pendingInviteProfile.last_name);
        expect(pendingInvite.gender).toBe(pendingInviteProfile.gender);
    });

    // ── Invited member access (new behaviour) ────────────────────────────────

    test('Invited member sees the family in the family list with user_status=invited', async ({ baseURL }) => {
        const response = await memberContext.get(`${baseURL}/api/v1/family`);
        const body = await expectCustomResponse(response, 200, true, null, 'Invited Member List Families');

        const families: any[] = body.data;
        const invitedFamily = families.find((f: any) => f.id === familyId);
        expect(invitedFamily).toBeDefined();
        expect(invitedFamily.user_status).toBe('invited');
        expect(invitedFamily.is_owner).toBe(false);
    });

    test('Invited member can view family detail without accepting', async ({ baseURL }) => {
        const response = await memberContext.get(`${baseURL}/api/v1/family/${familyId}`);
        const body = await expectCustomResponse(response, 200, true, null, 'Invited Member Family Detail');

        expect(body.data.id).toBe(familyId);
        expect(body.data.name).toBe('Test Family');
        // Invited member sees only JOINED members — pending/rejected not visible
        expect(Array.isArray(body.data.members)).toBe(true);
        const statuses: string[] = body.data.members.map((m: any) => m.status);
        statuses.forEach((s) => expect(s).toBe('joined'));
    });

    test('Invited member can list family members and sees only JOINED members', async ({ baseURL }) => {
        const response = await memberContext.get(`${baseURL}/api/v1/family/${familyId}/members/?limit=10&offset=0`);
        const body = await expectCustomResponse(response, 200, true, null, 'Invited Member List Members');

        expect(Array.isArray(body.data)).toBe(true);
        const statuses: string[] = body.data.map((m: any) => m.status);
        statuses.forEach((s) => expect(s).toBe('joined'));
    });

    // ── Member management ────────────────────────────────────────────────────

    test('Owner cannot add the same email twice', async ({ baseURL }) => {
        const payload = { email: process.env.TEST_ADMIN_EMAIL!, relation: 'friend' };
        const response = await ownerContext.post(`${baseURL}/api/v1/family/${familyId}/members`, { data: payload });
        const body = await expectCustomResponse(response, 400, false, payload, 'Duplicate Member');
        expect(body.error).toBeDefined();
    });

    test('Owner must provide invitee profile fields when the email has no user account', async ({ baseURL }) => {
        const payload = {
            email: `missing.family.${randomUUID()}@example.com`,
            relation: 'cousin',
        };

        const response = await ownerContext.post(`${baseURL}/api/v1/family/${familyId}/members`, { data: payload });
        const body = await expectCustomResponse(response, 400, false, payload, 'Missing Invitee Profile');

        const detailFields = new Set((body.error?.details || []).map((detail: any) => detail.field));
        expect(detailFields.has('first_name')).toBe(true);
        expect(detailFields.has('last_name')).toBe(true);
        expect(detailFields.has('gender')).toBe(true);
    });

    test('Owner can list family members (flat array response)', async ({ baseURL }) => {
        const response = await ownerContext.get(`${baseURL}/api/v1/family/${familyId}/members/?limit=10&offset=0`);
        const body = await expectCustomResponse(response, 200, true, null, 'List Members');

        // CustomListCreateAPIView returns data as a flat array (not {results: [...]})
        expect(Array.isArray(body.data)).toBe(true);
        const emails = body.data.map((m: any) => m.email);
        expect(emails).toContain(process.env.TEST_ADMIN_EMAIL);

        // Owner must see invited members (admin is still invited at this point)
        const adminEntry = body.data.find((m: any) => m.email === process.env.TEST_ADMIN_EMAIL);
        expect(adminEntry).toBeDefined();
        expect(adminEntry.status).toBe('invited');
        expect(adminEntry.first_name).not.toBe(ignoredExistingUserProfile.first_name);
        expect(adminEntry.last_name).not.toBe(ignoredExistingUserProfile.last_name);
        expect(adminEntry.gender).not.toBe(ignoredExistingUserProfile.gender);

        const pendingInvite = body.data.find((m: any) => m.email === pendingInviteEmail);
        expect(pendingInvite).toBeDefined();
        expect(pendingInvite.user).toBeNull();
        expect(pendingInvite.first_name).toBe(pendingInviteProfile.first_name);
        expect(pendingInvite.last_name).toBe(pendingInviteProfile.last_name);
        expect(pendingInvite.gender).toBe(pendingInviteProfile.gender);
    });

    // ── Old invitations list endpoint removed ────────────────────────────────

    test('Old v1/family/invitations list endpoint is no longer available (404)', async ({ baseURL }) => {
        const response = await memberContext.get(`${baseURL}/api/v1/family/invitations`);
        // Django will return 404 since there is no route matching this path
        expect([404]).toContain(response.status());
    });

    // ── Accept invitation (new URL: family-scoped) ───────────────────────────

    test('Member can accept the family invitation via family-scoped URL', async ({ baseURL }) => {
        const response = await memberContext.post(`${baseURL}/api/v1/family/${familyId}/accept`);
        const body = await expectCustomResponse(response, 200, true, null, 'Accept Invitation');
        expect(body.data.status).toBe('joined');
        expect(body.data.family).toBe(familyId);
    });

    test('Accept with invalid (non-existent) family id returns 404', async ({ baseURL }) => {
        const response = await memberContext.post(`${baseURL}/api/v1/family/${randomUUID()}/accept`);
        const body = await expectCustomResponse(response, 404, false, null, 'Accept Invitation Not Found');
        expect(body.error.code).toBe('NOT_FOUND');
    });

    test('Non-owner member sees only JOINED members when listing family members after accepting', async ({ baseURL }) => {
        const response = await memberContext.get(`${baseURL}/api/v1/family/${familyId}/members/?limit=10&offset=0`);
        const body = await expectCustomResponse(response, 200, true, null, 'Member List Members');

        expect(Array.isArray(body.data)).toBe(true);
        // Non-owners must never see invited/rejected entries — every record must be joined
        const statuses: string[] = body.data.map((m: any) => m.status);
        statuses.forEach((s) => expect(s).toBe('joined'));
    });

    test('Member sees joined family with is_owner=false and user_status=joined', async ({ baseURL }) => {
        const response = await memberContext.get(`${baseURL}/api/v1/family`);
        const body = await expectCustomResponse(response, 200, true, null, 'Member List Families');

        const families: any[] = body.data;
        const joined = families.find((f: any) => f.id === familyId);
        expect(joined).toBeDefined();
        expect(joined.is_owner).toBe(false);
        expect(joined.user_status).toBe('joined');
    });

    // ── Decline invitation + reject workflow ─────────────────────────────────

    test('Owner can invite a member who then declines — status becomes rejected', async ({ baseURL }) => {
        // Member exits first so they can be re-invited
        const exitRes = await memberContext.post(`${baseURL}/api/v1/family/${familyId}/exit`);
        expect([200, 400]).toContain(exitRes.status());

        // Re-invite
        const reInviteRes = await ownerContext.post(`${baseURL}/api/v1/family/${familyId}/members`, {
            data: { email: process.env.TEST_ADMIN_EMAIL!, relation: 'friend' },
        });
        const reInviteBody = await reInviteRes.json();
        expect(reInviteBody.success).toBe(true);
        familyMemberId = reInviteBody.data.id;

        // Member declines via new family-scoped URL
        const declineRes = await memberContext.post(`${baseURL}/api/v1/family/${familyId}/decline`);
        const declineBody = await expectCustomResponse(declineRes, 200, true, null, 'Decline Invitation');
        expect(declineBody.data.status).toBe('rejected');
        expect(declineBody.data.family).toBe(familyId);
    });

    test('Owner sees rejected member in members list with status=rejected', async ({ baseURL }) => {
        const response = await ownerContext.get(`${baseURL}/api/v1/family/${familyId}/members/?limit=20&offset=0`);
        const body = await expectCustomResponse(response, 200, true, null, 'Owner sees rejected member');

        const adminEntry = body.data.find((m: any) => m.email === process.env.TEST_ADMIN_EMAIL);
        expect(adminEntry).toBeDefined();
        expect(adminEntry.status).toBe('rejected');
    });

    test('Rejected member cannot access family detail (403 or 404)', async ({ baseURL }) => {
        const response = await memberContext.get(`${baseURL}/api/v1/family/${familyId}`);
        expect([403, 404]).toContain(response.status());
    });

    test('Rejected member does not see the family in their family list', async ({ baseURL }) => {
        const response = await memberContext.get(`${baseURL}/api/v1/family`);
        const body = await expectCustomResponse(response, 200, true, null, 'Rejected member family list');

        const families: any[] = body.data;
        const found = families.find((f: any) => f.id === familyId);
        expect(found).toBeUndefined();
    });

    test('Decline with invalid family id returns 404', async ({ baseURL }) => {
        const response = await memberContext.post(`${baseURL}/api/v1/family/${randomUUID()}/decline`);
        const body = await expectCustomResponse(response, 404, false, null, 'Decline Invitation Not Found');
        expect(body.error.code).toBe('NOT_FOUND');
        expect(body.error.message).toBe('The requested resource was not found.');
    });

    // ── Owner permanently removes rejected member record ──────────────────────

    test('Owner can permanently delete a rejected member record', async ({ baseURL }) => {
        // Fetch the rejected member's ID from the member list
        const listRes = await ownerContext.get(`${baseURL}/api/v1/family/${familyId}/members/?limit=20&offset=0`);
        const listBody = await listRes.json();
        const rejectedEntry = listBody.data.find((m: any) => m.email === process.env.TEST_ADMIN_EMAIL);
        expect(rejectedEntry).toBeDefined();
        expect(rejectedEntry.status).toBe('rejected');

        const rejectedMemberId = rejectedEntry.id;

        const deleteRes = await ownerContext.delete(
            `${baseURL}/api/v1/family/${familyId}/members/${rejectedMemberId}`,
        );
        expect([200, 204]).toContain(deleteRes.status());
    });

    test('Deleted rejected member no longer appears in the members list', async ({ baseURL }) => {
        const response = await ownerContext.get(`${baseURL}/api/v1/family/${familyId}/members/?limit=20&offset=0`);
        const body = await expectCustomResponse(response, 200, true, null, 'List after delete rejected');

        const adminEntry = body.data.find((m: any) => m.email === process.env.TEST_ADMIN_EMAIL);
        expect(adminEntry).toBeUndefined();
    });

    // ── Re-invite after hard delete creates a fresh record ────────────────────

    test('Owner can re-invite after permanent deletion — creates a fresh invite record', async ({ baseURL }) => {
        const oldMemberId = familyMemberId; // the rejected-then-deleted record

        const reInviteRes = await ownerContext.post(`${baseURL}/api/v1/family/${familyId}/members`, {
            data: { email: process.env.TEST_ADMIN_EMAIL!, relation: 'friend' },
        });
        const reInviteBody = await reInviteRes.json();
        expect(reInviteBody.success).toBe(true);
        expect(reInviteBody.data.status).toBe('invited');

        // The new member record must have a different ID — confirms it is a fresh create
        expect(reInviteBody.data.id).not.toBe(oldMemberId);
        familyMemberId = reInviteBody.data.id;
    });

    test('Re-invited member (after hard delete) sees the family with user_status=invited', async ({ baseURL }) => {
        const response = await memberContext.get(`${baseURL}/api/v1/family`);
        const body = await expectCustomResponse(response, 200, true, null, 'Re-invited member family list');

        const families: any[] = body.data;
        const invitedFamily = families.find((f: any) => f.id === familyId);
        expect(invitedFamily).toBeDefined();
        expect(invitedFamily.user_status).toBe('invited');
    });

    test('Re-invited member can accept the fresh invitation', async ({ baseURL }) => {
        const acceptRes = await memberContext.post(`${baseURL}/api/v1/family/${familyId}/accept`);
        const acceptBody = await expectCustomResponse(acceptRes, 200, true, null, 'Re-invite Accept');
        expect(acceptBody.data.status).toBe('joined');
    });

    test('Member can exit the family', async ({ baseURL }) => {
        const response = await memberContext.post(`${baseURL}/api/v1/family/${familyId}/exit`);
        await expectCustomResponse(response, 200, true, null, 'Exit Family');
    });

    // ── Deletion ─────────────────────────────────────────────────────────────

    test('Owner can delete the family', async ({ baseURL }) => {
        await logRequestPayload('DELETE', `${baseURL}/api/v1/family/${familyId}`, null, 'Delete Family');
        const response = await ownerContext.delete(`${baseURL}/api/v1/family/${familyId}`);
        expect([200, 204]).toContain(response.status());
        const body = await response.json().catch(() => ({}));
        await attachResponseToReport(body, 'Delete Family');
        deletedFamilyId = familyId;
        familyId = ''; // prevent afterAll from attempting a second delete
    });

    test('Deleted family is no longer accessible', async ({ baseURL }) => {
        await logRequestPayload('GET', `${baseURL}/api/v1/family/${deletedFamilyId}`, null, 'Get Deleted Family');
        const response = await ownerContext.get(`${baseURL}/api/v1/family/${deletedFamilyId}`);
        expect([403, 404]).toContain(response.status());
        const body = await response.json().catch(() => ({}));
        await attachResponseToReport(body, 'Get Deleted Family');
    });
});
