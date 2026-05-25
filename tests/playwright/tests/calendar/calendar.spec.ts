/**
 * Calendar API Tests — Events, Tasks, Comments, Unified View
 *
 * Coverage:
 *   - Full CRUD for events and tasks
 *   - All three access-control modes: only_me | group (family, close_group) | specific
 *   - Positive and negative access-control assertions
 *   - Recurring events/tasks via rrule (create + expand filter)
 *   - PUT /tasks/{id}/status for status updates; PUT /tasks/{id}/status/acknowledge for acknowledgment
 *   - Nested comments: POST/GET /events/{id}/comments/, /tasks/{id}/comments/
 *   - DELETE /comments/{id}/
 *   - Unified calendar view with from_date/to_date (GET only)
 *   - Validation edge-cases: missing required fields, naive datetime, invalid rrule
 *   - Auth guard: unauthenticated requests rejected
 *   - Authorization: non-creator cannot mutate another user's records
 *
 * NOTE: All shared resources are created in beforeAll to avoid Playwright's
 * nested-describe lifecycle re-running the hook between sections.
 * Tests are flat inside a single test.describe.
 */

import { test, expect, type APIRequestContext } from '@playwright/test';
import {
    getUserContext,
    getAdminContext,
    expectCustomResponse,
    logRequestPayload,
    attachResponseToReport,
} from '../../utils/api-client';

// ─── module-level shared state ─────────────────────────────────────────────────
let userCtx: APIRequestContext;
let adminCtx: APIRequestContext;

let userId: string;
let adminUserId: string;
let familyId: string;

// Events created in beforeAll
let eventIdOnlyMe: string;
let eventIdGroup: string;
let eventIdCloseGroup: string;
let eventIdSpecific: string;
let eventIdRecurring: string;

// Tasks created in beforeAll
let taskIdOnlyMe: string;
let taskIdGroup: string;
let taskIdSpecific: string;

// Close group ID
let closeGroupId: string;

// Comment IDs set during tests
let eventCommentId: string;
let taskCommentId: string;

// ─── helpers ──────────────────────────────────────────────────────────────────
async function deleteAll(ctx: APIRequestContext, base: string, path: string) {
    const res = await ctx.get(`${base}${path}?page_size=100`);
    const body = await res.json().catch(() => ({ data: [] }));
    const items: any[] = body?.data ?? [];
    for (const item of items) {
        await ctx.delete(`${base}${path}/${item.id}`).catch(() => {});
    }
}

function buildCreatedEventsQuery(date: string) {
    return `?from_date=${date}&to_date=${date}&creator_id=${userId}&page_size=5000`;
}

function buildCreatedTasksQuery() {
    return `?creator_id=${userId}&page_size=1000`;
}

async function uploadTempFile(ctx: APIRequestContext, baseURL: string, fileName = 'calendar-attachment.txt', contents = 'calendar attachment') {
    const response = await ctx.post(`${baseURL}/api/v1/upload`, {
        multipart: {
            file: {
                name: fileName,
                mimeType: 'text/plain',
                buffer: Buffer.from(contents),
            },
        },
    });
    const body = await expectCustomResponse(response, 201, true, { file: `${fileName} (text/plain)` }, 'Calendar attachment upload');
    return body.data.path;
}

function occurrenceDates(items: any[], title: string, dateField: 'start_at' | 'deadline_datetime' = 'start_at') {
    return items
        .filter((item: any) => item.title === title)
        .map((item: any) => item[dateField].split('T')[0])
        .sort();
}

function itemsWithTitle(items: any[], title: string) {
    return items.filter((item: any) => item.title === title);
}

function expectSingleTitledItem(items: any[], title: string) {
    const matches = itemsWithTitle(items, title);
    expect(matches).toHaveLength(1);
    return matches[0];
}

function expectValidationField(details: any[], field: string, messageIncludes?: string) {
    const matches = (details ?? []).filter((detail: any) => detail?.field === field);
    expect(matches.length).toBeGreaterThan(0);
    if (messageIncludes) {
        expect(matches.some((detail: any) => String(detail?.message ?? '').includes(messageIncludes))).toBe(true);
    }
}

// ══════════════════════════════════════════════════════════════════════════════
test.describe('Calendar API', () => {

    test.beforeAll(async ({ baseURL }) => {
        test.setTimeout(120000);
        userCtx = await getUserContext();
        adminCtx = await getAdminContext();

        // Get user IDs
        const profileUser = await (await userCtx.get(`${baseURL}/api/v1/user/profile`)).json();
        userId = profileUser.data.id;

        const profileAdmin = await (await adminCtx.get(`${baseURL}/api/v1/user/profile`)).json();
        adminUserId = profileAdmin.data.id;

        // Clean slate
        await deleteAll(userCtx, baseURL!, '/api/v1/calendar/events');
        await deleteAll(userCtx, baseURL!, '/api/v1/calendar/tasks');
        await deleteAll(adminCtx, baseURL!, '/api/v1/calendar/events');
        await deleteAll(adminCtx, baseURL!, '/api/v1/calendar/tasks');

        // Family: owned by TEST_USER with TEST_ADMIN as a member
        const famListRes = await userCtx.get(`${baseURL}/api/v1/family`);
        const famListBody = await famListRes.json();
        const ownedFamily = (famListBody.data ?? []).find((f: any) => f.is_owner);
        if (ownedFamily) {
            familyId = ownedFamily.id;
        } else {
            const createFamRes = await userCtx.post(`${baseURL}/api/v1/family`, {
                data: { name: 'Calendar Test Family' },
            });
            familyId = (await createFamRes.json()).data.id;
        }
        await userCtx.post(`${baseURL}/api/v1/family/${familyId}/members`, {
            data: { email: process.env.TEST_ADMIN_EMAIL!, relation: 'friend' },
        }).catch(() => {});

        // Accept any pending family invitation from our family so admin has joined status
        const invRes = await adminCtx.get(`${baseURL}/api/v1/family/invitations`);
        const invBody = await invRes.json().catch(() => ({ data: [] }));
        const pendingInvite = (invBody.data ?? []).find((inv: any) => inv.family === familyId);
        if (pendingInvite) {
            await adminCtx.post(`${baseURL}/api/v1/family/invitations/${pendingInvite.id}/accept`);
        }

        // Close group: get default close group ID, then add TEST_ADMIN as member
        const cgListRes = await userCtx.get(`${baseURL}/api/v1/close-group`);
        const cgListBody = await cgListRes.json();
        closeGroupId = (cgListBody.data ?? [])[0]?.id;
        if (closeGroupId) {
            await userCtx.post(`${baseURL}/api/v1/close-group/${closeGroupId}/members`, {
                data: { email: process.env.TEST_ADMIN_EMAIL! },
            }).catch(() => {});
        }

        // ── Create shared test events ──────────────────────────────────────
        const e1 = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
            data: { title: 'Private Birthday', start_at: '2026-08-01T10:00:00Z', access_type: 'only_me' },
        });
        eventIdOnlyMe = (await e1.json()).data.id;

        const e2 = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
            data: {
                title: 'Family Dinner',
                start_at: '2026-08-10T18:00:00Z',
                access_type: 'mixed',
                access_family_ids: [familyId],
                access_close_group_ids: [],
            },
        });
        eventIdGroup = (await e2.json()).data.id;

        const e3 = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
            data: { title: 'Close Group Gathering', start_at: '2026-08-15T09:00:00Z', access_type: 'mixed', access_close_group_ids: closeGroupId ? [closeGroupId] : [], access_family_ids: [] },
        });
        eventIdCloseGroup = (await e3.json()).data.id;

        const e4 = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
            data: { title: 'One-on-One Appointment', start_at: '2026-08-20T14:00:00Z', access_type: 'mixed', access_user_ids: [adminUserId] },
        });
        eventIdSpecific = (await e4.json()).data.id;

        const e5 = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
            data: {
                title: 'Weekly Standup',
                start_at: '2026-08-04T09:00:00Z',
                end_at: '2026-08-04T09:30:00Z',
                access_type: 'mixed',
                access_family_ids: [familyId],
                rrule: { frequency: 'weekly', interval: 1, by_day: ['MO'], until: '2026-12-31' },
            },
        });
        eventIdRecurring = (await e5.json()).data.id;

        // ── Create shared test tasks ───────────────────────────────────────
        const t1 = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: { title: 'Buy Groceries', access_type: 'only_me', priority: 'medium' },
        });
        taskIdOnlyMe = (await t1.json()).data.id;

        const t2 = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: {
                title: 'Pay Electricity Bill',
                access_type: 'mixed',
                access_family_ids: [familyId],
                priority: 'high',
                deadline_datetime: '2026-08-25T18:00:00Z',
            },
        });
        taskIdGroup = (await t2.json()).data.id;

        const t3 = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: { title: 'Review Document', access_type: 'mixed', access_user_ids: [adminUserId] },
        });
        taskIdSpecific = (await t3.json()).data.id;
    });

    test.afterAll(async ({ baseURL }) => {
        test.setTimeout(120000);
        await deleteAll(userCtx, baseURL!, '/api/v1/calendar/events');
        await deleteAll(userCtx, baseURL!, '/api/v1/calendar/tasks');
        await deleteAll(adminCtx, baseURL!, '/api/v1/calendar/events');
        await deleteAll(adminCtx, baseURL!, '/api/v1/calendar/tasks');
    });

    // ══════════════════════════════════════════════════════════════════════════
    // SECTION 1 — EVENT CREATE (validation cases; CRUD events already in beforeAll)
    // ══════════════════════════════════════════════════════════════════════════

    test('Event create: only_me event created with correct fields', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/events/${eventIdOnlyMe}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Event — get only_me');
        expect(body.data.title).toBe('Private Birthday');
        expect(body.data.access_type).toBe('only_me');
        expect(body.data.start_at).toBeDefined();
        expect(body.data.end_at).toBeNull();
        expect(body.data.all_day).toBe(false);
        expect(body.data.comment_count).toBe(0);
    });

    test('Event create: group/family event has correct access_family_ids', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/events/${eventIdGroup}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Event — get group/family');
        expect(body.data.access_type).toBe('mixed');
        expect(body.data.access_family_ids).toContain(familyId);
    });

    test('Event create: close_group event has correct access_close_group_ids', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/events/${eventIdCloseGroup}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Event — get close_group');
        expect(body.data.access_type).toBe('mixed');
        expect(Array.isArray(body.data.access_close_group_ids)).toBe(true);
        if (closeGroupId) {
            expect(body.data.access_close_group_ids).toContain(closeGroupId);
        }
    });

    test('Event create: specific event has correct access_user_ids', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/events/${eventIdSpecific}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Event — get specific');
        expect(body.data.access_type).toBe('mixed');
        expect(body.data.access_user_ids).toContain(adminUserId);
    });

    test('Event create: recurring event has rrule fields and recurrence_end_date', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/events/${eventIdRecurring}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Event — get recurring');
        expect(body.data.rrule).toBeDefined();
        expect(body.data.rrule.frequency).toBe('weekly');
        expect(body.data.rrule.by_day).toContain('MO');
        expect(body.data.recurrence_end_date).toBe('2026-12-31');
    });

    test('Event create: explicit null end_at is accepted', async ({ baseURL }) => {
        const payload = { title: 'Null End Event', start_at: '2026-09-02T10:00:00Z', end_at: null, access_type: 'only_me' };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/events`, { data: payload });
        const body = await expectCustomResponse(res, 201, true, payload, 'Event create — null end_at');
        expect(body.data.end_at).toBeNull();
        await userCtx.delete(`${baseURL}/api/v1/calendar/events/${body.data.id}`);
    });

    test('Event create: reject end_at earlier than start_at', async ({ baseURL }) => {
        const payload = {
            title: 'Backwards Event',
            start_at: '2026-09-02T10:00:00Z',
            end_at: '2026-09-02T09:00:00Z',
            access_type: 'only_me',
        };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/events`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Event create — end_at before start_at');
        expectValidationField(body.error.details, 'end_at');
    });

    test('Event create: reject invalid attachment path', async ({ baseURL }) => {
        const payload = {
            title: 'Bad Attachment Event',
            start_at: '2026-09-02T10:00:00Z',
            access_type: 'only_me',
            attachments: ['temp/unknown/missing.txt'],
        };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/events`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Event create — invalid attachment');
        expectValidationField(body.error.details, 'attachments');
    });

    test('Event create: moves uploaded temp attachment into events folder', async ({ baseURL }) => {
        const attachmentPath = await uploadTempFile(userCtx, baseURL!, 'event-attachment.txt', 'event attachment');
        const payload = {
            title: 'Attachment Event',
            start_at: '2026-09-03T10:00:00Z',
            access_type: 'only_me',
            attachments: [attachmentPath],
        };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/events`, { data: payload });
        const body = await expectCustomResponse(res, 201, true, payload, 'Event create — attachment move');
        expect(body.data.attachments[0]).toMatch(/^events\//);
        await userCtx.delete(`${baseURL}/api/v1/calendar/events/${body.data.id}`);
    });

    // ── Event create validation failures ──────────────────────────────────────

    test('Event create: reject missing title', async ({ baseURL }) => {
        const payload = { start_at: '2026-09-01T10:00:00Z', access_type: 'only_me' };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/events`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Event create — missing title');
        expectValidationField(body.error.details, 'title');
    });

    test('Event create: reject missing start_at', async ({ baseURL }) => {
        const payload = { title: 'No Start', access_type: 'only_me' };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/events`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Event create — missing start_at');
        expectValidationField(body.error.details, 'start_at');
    });

    test('Event create: reject naive (timezone-unaware) datetime', async ({ baseURL }) => {
        const payload = { title: 'Bad DateTime', start_at: '2026-09-01T10:00:00', access_type: 'only_me' };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/events`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Event create — naive datetime');
        expectValidationField(body.error.details, 'start_at');
    });

    test('Event create: reject mixed with no family, close_group or user target', async ({ baseURL }) => {
        const payload = { title: 'No Target', start_at: '2026-09-01T10:00:00Z', access_type: 'mixed', access_family_ids: [], access_close_group_ids: [], access_user_ids: [] };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/events`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Event create — mixed no target');
        expectValidationField(body.error.details, 'access_type');
    });

    test('Event create: reject mixed with empty access_user_ids only', async ({ baseURL }) => {
        const payload = { title: 'No Users', start_at: '2026-09-01T10:00:00Z', access_type: 'mixed', access_family_ids: [], access_close_group_ids: [], access_user_ids: [] };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/events`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Event create — mixed no users');
        expectValidationField(body.error.details, 'access_type');
    });

    test('Event create: reject specific user outside family and close group', async ({ baseURL }) => {
        const payload = {
            title: 'Outside Specific Event',
            start_at: '2026-09-01T10:00:00Z',
            access_type: 'mixed',
            access_user_ids: ['00000000-0000-0000-0000-000000000123'],
        };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/events`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Event create — specific outside graph');
        expectValidationField(body.error.details, 'access_user_ids');
    });

    test('Event create: reject rrule with both count and until', async ({ baseURL }) => {
        const payload = { title: 'Ambiguous', start_at: '2026-09-01T10:00:00Z', access_type: 'only_me', rrule: { frequency: 'weekly', count: 10, until: '2026-12-31' } };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/events`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Event create — rrule count+until');
        expect(body.error.details.length).toBeGreaterThan(0);
    });

    test('Event create: reject recurring event with no until', async ({ baseURL }) => {
        const payload = { title: 'No End Date', start_at: '2026-09-01T10:00:00Z', access_type: 'only_me', rrule: { frequency: 'weekly', interval: 1 } };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/events`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Event create — rrule without until');
        expectValidationField(body.error.details, 'rrule.until');
    });

    test('Event create: unauthenticated request rejected', async ({ request, baseURL }) => {
        const payload = { title: 'Hacker', start_at: '2026-09-01T10:00:00Z', access_type: 'only_me' };
        const res = await request.post(`${baseURL}/api/v1/calendar/events`, { data: payload });
        expect([401, 403]).toContain(res.status());
    });

    // ══════════════════════════════════════════════════════════════════════════
    // SECTION 2 — EVENT LIST + ACCESS CONTROL
    // ══════════════════════════════════════════════════════════════════════════

    test('Event list: creator sees own only_me event', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/events/${buildCreatedEventsQuery('2026-08-01')}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Event list — creator sees only_me');
        const ids = body.data.map((e: any) => e.id);
        expect(ids).toContain(eventIdOnlyMe);
    });

    test('Event list: member CANNOT see only_me event', async ({ baseURL }) => {
        const res = await adminCtx.get(`${baseURL}/api/v1/calendar/events/${buildCreatedEventsQuery('2026-08-01')}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Event list — member cannot see only_me');
        const ids = body.data.map((e: any) => e.id);
        expect(ids).not.toContain(eventIdOnlyMe);
    });

    test('Event list: member CAN see group/family event', async ({ baseURL }) => {
        const res = await adminCtx.get(`${baseURL}/api/v1/calendar/events/${buildCreatedEventsQuery('2026-08-10')}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Event list — member sees group/family');
        const ids = body.data.map((e: any) => e.id);
        expect(ids).toContain(eventIdGroup);
    });

    test('Event list: member CAN see close_group event', async ({ baseURL }) => {
        const res = await adminCtx.get(`${baseURL}/api/v1/calendar/events/${buildCreatedEventsQuery('2026-08-15')}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Event list — member sees close_group');
        const ids = body.data.map((e: any) => e.id);
        expect(ids).toContain(eventIdCloseGroup);
    });

    test('Event list: named user CAN see specific event', async ({ baseURL }) => {
        const res = await adminCtx.get(`${baseURL}/api/v1/calendar/events/${buildCreatedEventsQuery('2026-08-20')}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Event list — named user sees specific');
        const ids = body.data.map((e: any) => e.id);
        expect(ids).toContain(eventIdSpecific);
    });

    test('Event list: items include detail fields except comments array', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/events/${buildCreatedEventsQuery('2026-08-10')}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Event list — detail shape');
        expect(body.data.length).toBeGreaterThan(0);
        const item = body.data[0];
        expect(item).toHaveProperty('description');
        expect(item).toHaveProperty('access_family_ids');
        expect(item).toHaveProperty('access_close_group_ids');
        expect(item).toHaveProperty('access_user_ids');
        expect(item).toHaveProperty('attachments');
        expect(item).toHaveProperty('parent_event_id');
        expect(item).toHaveProperty('occurrence_date');
        expect(item).toHaveProperty('comment_count');
        expect(item).toHaveProperty('updated_at');
        expect(item).not.toHaveProperty('comments');
    });

    test('Event list: non-named user CANNOT see specific-to-self event', async ({ baseURL }) => {
        // Create an event specific to userId only, verify adminCtx cannot see it
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
            data: { title: 'Secret for User Only', start_at: '2026-09-25T10:00:00Z', access_type: 'mixed', access_user_ids: [userId] },
        });
        const privateId = (await createRes.json()).data.id;

        const res = await adminCtx.get(`${baseURL}/api/v1/calendar/events`);
        const body = await expectCustomResponse(res, 200, true, null, 'Event list — admin cannot see self-specific');
        expect(body.data.map((e: any) => e.id)).not.toContain(privateId);

        await userCtx.delete(`${baseURL}/api/v1/calendar/events/${privateId}`);
    });

    test('Event list: from_date/to_date filter', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/events/?from_date=2026-08-01&to_date=2026-08-05`);
        const body = await expectCustomResponse(res, 200, true, null, 'Event list — date filter');
        for (const e of body.data) {
            const d = e.start_at.split('T')[0];
            expect(d >= '2026-08-01').toBe(true);
            expect(d <= '2026-08-05').toBe(true);
        }
    });

    test('Event list: access_type filter', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/events/?access_type=only_me`);
        const body = await expectCustomResponse(res, 200, true, null, 'Event list — access_type filter');
        for (const e of body.data) {
            expect(e.access_type).toBe('only_me');
        }
    });

    test('Event list: pagination', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/events/?page=1&page_size=2`);
        const body = await expectCustomResponse(res, 200, true, null, 'Event list — pagination');
        expect(body.meta).toHaveProperty('total');
        expect(body.meta).toHaveProperty('page');
        expect(body.meta).toHaveProperty('page_size');
        expect(body.meta).toHaveProperty('total_pages');
        expect(body.data.length).toBeLessThanOrEqual(2);
    });

    // ══════════════════════════════════════════════════════════════════════════
    // SECTION 3 — EVENT DETAIL / UPDATE / DELETE
    // ══════════════════════════════════════════════════════════════════════════

    test('Event detail: creator can get event with comments field', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/events/${eventIdGroup}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Event detail — creator');
        expect(body.data.id).toBe(eventIdGroup);
        expect(body.data).toHaveProperty('comment_count');
        expect(body.data).toHaveProperty('comments');
    });

    test('Event detail: member can get group event', async ({ baseURL }) => {
        const res = await adminCtx.get(`${baseURL}/api/v1/calendar/events/${eventIdGroup}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Event detail — member gets group event');
        expect(body.data.id).toBe(eventIdGroup);
    });

    test('Event detail: member gets 404 on only_me event', async ({ baseURL }) => {
        await logRequestPayload('GET', `${baseURL}/api/v1/calendar/events/${eventIdOnlyMe}`, null, 'Event detail — only_me by non-creator');
        const res = await adminCtx.get(`${baseURL}/api/v1/calendar/events/${eventIdOnlyMe}`);
        const body = await res.json();
        await attachResponseToReport(body, 'Event detail — only_me by non-creator');
        expect(res.status()).toBe(404);
    });

    test('Event detail: non-existent returns 404', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/events/00000000-0000-0000-0000-000000000000`);
        expect(res.status()).toBe(404);
    });

    test('Event update: creator can update title', async ({ baseURL }) => {
        // Use a disposable event to avoid polluting shared state
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
            data: { title: 'Update Target', start_at: '2026-09-05T10:00:00Z', access_type: 'mixed', access_family_ids: [familyId] },
        });
        const updateId = (await createRes.json()).data.id;

        const payload = { title: 'Update Target (Updated)', start_at: '2026-09-05T10:00:00Z' };
        const res = await userCtx.put(`${baseURL}/api/v1/calendar/events/${updateId}`, { data: payload });
        const body = await expectCustomResponse(res, 200, true, payload, 'Event update — creator');
        expect(body.data.title).toBe('Update Target (Updated)');

        await userCtx.delete(`${baseURL}/api/v1/calendar/events/${updateId}`);
    });

    test('Event update: invalid update_scope returns 400', async ({ baseURL }) => {
        const payload = { title: 'Scope Test', update_scope: 'invalid_scope' };
        const res = await userCtx.put(`${baseURL}/api/v1/calendar/events/${eventIdRecurring}`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Event update — invalid update_scope');
        expectValidationField(body.error.details, 'update_scope');
    });

    test('Event update: update_scope=this without occurrence_date returns 400', async ({ baseURL }) => {
        const payload = { title: 'Missing Date', update_scope: 'this' };
        const res = await userCtx.put(`${baseURL}/api/v1/calendar/events/${eventIdRecurring}`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Event update — this without occurrence_date');
        expectValidationField(body.error.details, 'occurrence_date');
    });

    test('Event update: non-creator gets 403', async ({ baseURL }) => {
        const payload = { title: 'Hijacked', start_at: '2026-08-10T18:00:00Z' };
        await logRequestPayload('PUT', `${baseURL}/api/v1/calendar/events/${eventIdGroup}`, payload, 'Event update — non-creator');
        const res = await adminCtx.put(`${baseURL}/api/v1/calendar/events/${eventIdGroup}`, { data: payload });
        expect(res.status()).toBe(403);
    });

    test('Event delete: creator can delete, event gone after', async ({ baseURL }) => {
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
            data: { title: 'To Be Deleted', start_at: '2026-09-30T08:00:00Z', access_type: 'only_me' },
        });
        const disposableId = (await createRes.json()).data.id;

        const res = await userCtx.delete(`${baseURL}/api/v1/calendar/events/${disposableId}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Event delete — creator');
        expect(body.data.deleted).toBe(true);

        const getRes = await userCtx.get(`${baseURL}/api/v1/calendar/events/${disposableId}`);
        expect(getRes.status()).toBe(404);
    });

    test('Event delete: non-creator gets 403', async ({ baseURL }) => {
        await logRequestPayload('DELETE', `${baseURL}/api/v1/calendar/events/${eventIdGroup}`, null, 'Event delete — non-creator');
        const res = await adminCtx.delete(`${baseURL}/api/v1/calendar/events/${eventIdGroup}`);
        expect(res.status()).toBe(403);
    });

    // ══════════════════════════════════════════════════════════════════════════
    // SECTION 4 — RECURRING EVENT EXPANSION
    // ══════════════════════════════════════════════════════════════════════════

    test('Recurring: unified calendar returns weekly occurrences in range', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/?from_date=2026-08-04&to_date=2026-08-31`);
        const body = await expectCustomResponse(res, 200, true, null, 'Recurring — unified calendar summary');
        const events = body.data?.events ?? [];
        const recurringParent = expectSingleTitledItem(events, 'Weekly Standup');
        expect(recurringParent.rrule?.frequency).toBe('weekly');
        expect(recurringParent).not.toHaveProperty('parent_event_id');
        expect(recurringParent).not.toHaveProperty('occurrence_date');
    });

    test('Recurring: delete scope=this tombstones one occurrence, parent survives', async ({ baseURL }) => {
        // Create a fresh recurring event to mutate (to avoid touching shared eventIdRecurring)
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
            data: {
                title: 'Delete-This-Recur',
                start_at: '2026-09-07T09:00:00Z',
                access_type: 'only_me',
                rrule: { frequency: 'weekly', interval: 1, by_day: ['MO'], until: '2026-12-31' },
            },
        });
        const recurId = (await createRes.json()).data.id;

        const res = await userCtx.delete(`${baseURL}/api/v1/calendar/events/${recurId}/?scope=this&occurrence_date=2026-09-07`);
        const body = await expectCustomResponse(res, 200, true, null, 'Recurring — delete scope=this');
        expect(body.data.deleted).toBe(true);

        // Parent still exists
        const getRes = await userCtx.get(`${baseURL}/api/v1/calendar/events/${recurId}`);
        expect(getRes.status()).toBe(200);

        await userCtx.delete(`${baseURL}/api/v1/calendar/events/${recurId}`);
    });

    test('Recurring: update scope=this_and_future creates new child series', async ({ baseURL }) => {
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
            data: {
                title: 'Split-Recur',
                start_at: '2026-09-07T09:00:00Z',
                access_type: 'only_me',
                rrule: { frequency: 'weekly', interval: 1, by_day: ['MO'], until: '2026-12-31' },
            },
        });
        const recurId = (await createRes.json()).data.id;

        const payload = { title: 'Split-Recur (New Series)', update_scope: 'this_and_future', occurrence_date: '2026-09-21', start_at: '2026-09-21T09:00:00Z' };
        const res = await userCtx.put(`${baseURL}/api/v1/calendar/events/${recurId}`, { data: payload });
        const body = await expectCustomResponse(res, 200, true, payload, 'Recurring — scope=this_and_future');
        expect(body.data.title).toBe('Split-Recur (New Series)');

        // Clean up both parent and new child
        await userCtx.delete(`${baseURL}/api/v1/calendar/events/${recurId}`).catch(() => {});
        await userCtx.delete(`${baseURL}/api/v1/calendar/events/${body.data.id}`).catch(() => {});
    });

    test('Recurring: delete scope=this — tombstoned occurrence absent from expanded list', async ({ baseURL }) => {
        const title = `Delete-Occurrence-Verify ${Date.now()}`;
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
            data: {
                title,
                start_at: '2026-09-07T09:00:00Z',
                access_type: 'only_me',
                rrule: { frequency: 'weekly', interval: 1, by_day: ['MO'], until: '2026-12-31' },
            },
        });
        const recurId = (await createRes.json()).data.id;

        // Delete the 2026-09-14 occurrence
        const deleteRes = await userCtx.delete(
            `${baseURL}/api/v1/calendar/events/${recurId}?scope=this&occurrence_date=2026-09-14`,
        );
        await expectCustomResponse(deleteRes, 200, true, null, 'Recurring — delete single occurrence');

        // Expand the week containing that date — deleted occurrence must be absent
        const listRes = await userCtx.get(
            `${baseURL}/api/v1/calendar/day?date=2026-09-14`,
        );
        const listBody = await expectCustomResponse(listRes, 200, true, null, 'Recurring — day after tombstone');
        expect(itemsWithTitle(listBody.data.events ?? [], title)).toHaveLength(0);

        // A different occurrence (2026-09-21) is still present
        const nextDayRes = await userCtx.get(`${baseURL}/api/v1/calendar/day?date=2026-09-21`);
        const nextDayBody = await expectCustomResponse(nextDayRes, 200, true, null, 'Recurring — next occurrence still present');
        expect(itemsWithTitle(nextDayBody.data.events ?? [], title)).toHaveLength(1);

        await userCtx.delete(`${baseURL}/api/v1/calendar/events/${recurId}`);
    });

    test('Recurring: delete scope=this_and_future truncates event series', async ({ baseURL }) => {
        const title = `Delete-Future-Events ${Date.now()}`;
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
            data: {
                title,
                start_at: '2026-09-07T09:00:00Z',
                access_type: 'only_me',
                rrule: { frequency: 'weekly', interval: 1, by_day: ['MO'], until: '2026-12-31' },
            },
        });
        const recurId = (await createRes.json()).data.id;

        // Truncate from 2026-09-21 onwards — 2026-09-14 should remain
        const deleteRes = await userCtx.delete(
            `${baseURL}/api/v1/calendar/events/${recurId}?scope=this_and_future&occurrence_date=2026-09-21`,
        );
        await expectCustomResponse(deleteRes, 200, true, null, 'Recurring — delete this_and_future');

        // 2026-09-14 still exists
        const beforeRes = await userCtx.get(`${baseURL}/api/v1/calendar/day?date=2026-09-14`);
        const beforeBody = await expectCustomResponse(beforeRes, 200, true, null, 'Recurring — occurrence before cut survives');
        expect(itemsWithTitle(beforeBody.data.events ?? [], title)).toHaveLength(1);

        // 2026-09-21 (the cut point) is gone
        const cutRes = await userCtx.get(`${baseURL}/api/v1/calendar/day?date=2026-09-21`);
        const cutBody = await expectCustomResponse(cutRes, 200, true, null, 'Recurring — cut occurrence gone');
        expect(itemsWithTitle(cutBody.data.events ?? [], title)).toHaveLength(0);

        await userCtx.delete(`${baseURL}/api/v1/calendar/events/${recurId}`);
    });

    test('Recurring: delete scope=this without occurrence_date returns 400', async ({ baseURL }) => {
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
            data: {
                title: 'Scope-Delete-Validation',
                start_at: '2026-09-07T09:00:00Z',
                access_type: 'only_me',
                rrule: { frequency: 'weekly', interval: 1, until: '2026-12-31' },
            },
        });
        const recurId = (await createRes.json()).data.id;

        const res = await userCtx.delete(`${baseURL}/api/v1/calendar/events/${recurId}?scope=this`);
        const body = await expectCustomResponse(res, 400, false, null, 'Recurring — delete scope=this missing occurrence_date');
        expectValidationField(body.error.details, 'occurrence_date');

        await userCtx.delete(`${baseURL}/api/v1/calendar/events/${recurId}`);
    });

    // ══════════════════════════════════════════════════════════════════════════
    // SECTION 5 — TASK CREATE (validation cases; CRUD tasks already in beforeAll)
    // ══════════════════════════════════════════════════════════════════════════

    test('Task create: only_me task created with correct fields', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/tasks/${taskIdOnlyMe}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Task — get only_me');
        expect(body.data.status).toBe('pending');
        expect(body.data.is_visible).toBe(true);
        expect(body.data.completed_at).toBeNull();
        expect(body.data.acknowledged_at).toBeNull();
        expect(body.data.comment_count).toBe(0);
    });

    test('Task create: group/family task has correct priority', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/tasks/${taskIdGroup}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Task — get group/family');
        expect(body.data.priority).toBe('high');
        expect(body.data.access_type).toBe('mixed');
    });

    test('Task create: recurring task has rrule and recurrence_end_date', async ({ baseURL }) => {
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: { title: 'Weekly Report', access_type: 'mixed', access_family_ids: [familyId], deadline_datetime: '2026-08-07T17:00:00Z', rrule: { frequency: 'weekly', interval: 1, by_day: ['FR'], until: '2026-09-30' } },
        });
        const body = await expectCustomResponse(createRes, 201, true, null, 'Task create — recurring');
        expect(body.data.rrule.frequency).toBe('weekly');
        expect(body.data.recurrence_end_date).toBe('2026-09-30');
        await userCtx.delete(`${baseURL}/api/v1/calendar/tasks/${body.data.id}`);
    });

    test('Task create: reject recurring task with count but no until', async ({ baseURL }) => {
        const payload = { title: 'Count Only Task', access_type: 'only_me', rrule: { frequency: 'weekly', interval: 1, count: 8 } };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Task create — rrule count without until');
        expectValidationField(body.error.details, 'rrule.until');
    });

    // ── Task create validation failures ───────────────────────────────────────

    test('Task create: reject missing title', async ({ baseURL }) => {
        const payload = { access_type: 'only_me' };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Task create — missing title');
        expectValidationField(body.error.details, 'title');
    });

    test('Task create: reject naive deadline_datetime', async ({ baseURL }) => {
        const payload = { title: 'Bad Deadline', access_type: 'only_me', deadline_datetime: '2026-08-25T18:00:00' };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Task create — naive deadline');
        expectValidationField(body.error.details, 'deadline_datetime');
    });

    test('Task create: reject specific user outside family and close group', async ({ baseURL }) => {
        const payload = {
            title: 'Outside Specific Task',
            access_type: 'mixed',
            access_user_ids: ['00000000-0000-0000-0000-000000000123'],
        };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Task create — specific outside graph');
        expectValidationField(body.error.details, 'access_user_ids');
    });

    test('Task create: reject invalid rrule frequency', async ({ baseURL }) => {
        const payload = { title: 'Bad Freq', access_type: 'only_me', rrule: { frequency: 'hourly' } };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Task create — invalid rrule freq');
        expect(body.error.details.length).toBeGreaterThan(0);
    });

    test('Task create: reject invalid attachment path', async ({ baseURL }) => {
        const payload = {
            title: 'Bad Attachment Task',
            access_type: 'only_me',
            attachments: ['temp/unknown/missing.txt'],
        };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Task create — invalid attachment');
        expectValidationField(body.error.details, 'attachments');
    });

    test('Task create: moves uploaded temp attachment into tasks folder', async ({ baseURL }) => {
        const attachmentPath = await uploadTempFile(userCtx, baseURL!, 'task-attachment.txt', 'task attachment');
        const payload = {
            title: 'Attachment Task',
            access_type: 'only_me',
            attachments: [attachmentPath],
        };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, { data: payload });
        const body = await expectCustomResponse(res, 201, true, payload, 'Task create — attachment move');
        expect(body.data.attachments[0]).toMatch(/^tasks\//);
        await userCtx.delete(`${baseURL}/api/v1/calendar/tasks/${body.data.id}`);
    });

    test('Task create: unauthenticated request rejected', async ({ request, baseURL }) => {
        const res = await request.post(`${baseURL}/api/v1/calendar/tasks`, { data: { title: 'Hack', access_type: 'only_me' } });
        expect([401, 403]).toContain(res.status());
    });

    // ══════════════════════════════════════════════════════════════════════════
    // SECTION 6 — TASK LIST + ACCESS CONTROL
    // ══════════════════════════════════════════════════════════════════════════

    test('Task list: creator sees own only_me task', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/tasks/${buildCreatedTasksQuery()}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Task list — creator sees only_me');
        expect(body.data.map((t: any) => t.id)).toContain(taskIdOnlyMe);
    });

    test('Task list: member CANNOT see only_me task', async ({ baseURL }) => {
        const res = await adminCtx.get(`${baseURL}/api/v1/calendar/tasks/${buildCreatedTasksQuery()}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Task list — member cannot see only_me');
        expect(body.data.map((t: any) => t.id)).not.toContain(taskIdOnlyMe);
    });

    test('Task list: member CAN see group/family task', async ({ baseURL }) => {
        const res = await adminCtx.get(`${baseURL}/api/v1/calendar/tasks/${buildCreatedTasksQuery()}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Task list — member sees group/family');
        expect(body.data.map((t: any) => t.id)).toContain(taskIdGroup);
    });

    test('Task list: named user CAN see specific task', async ({ baseURL }) => {
        const res = await adminCtx.get(`${baseURL}/api/v1/calendar/tasks/${buildCreatedTasksQuery()}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Task list — named user sees specific');
        expect(body.data.map((t: any) => t.id)).toContain(taskIdSpecific);
    });

    test('Task list: items include detail fields except comments array', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/tasks/${buildCreatedTasksQuery()}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Task list — detail shape');
        expect(body.data.length).toBeGreaterThan(0);
        const item = body.data[0];
        expect(item).toHaveProperty('description');
        expect(item).toHaveProperty('access_type');
        expect(item).toHaveProperty('access_family_ids');
        expect(item).toHaveProperty('access_close_group_ids');
        expect(item).toHaveProperty('access_user_ids');
        expect(item).toHaveProperty('done_by');
        expect(item).toHaveProperty('attachments');
        expect(item).toHaveProperty('parent_task_id');
        expect(item).toHaveProperty('occurrence_date');
        expect(item).toHaveProperty('comment_count');
        expect(item).toHaveProperty('updated_at');
        expect(item).not.toHaveProperty('comments');
    });

    test('Task list: non-named user CANNOT see task specific to another user', async ({ baseURL }) => {
        const createRes = await adminCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: { title: 'Invisible Task', access_type: 'mixed', access_user_ids: [adminUserId] },
        });
        const privateId = (await createRes.json()).data.id;

        const res = await userCtx.get(`${baseURL}/api/v1/calendar/tasks`);
        const body = await expectCustomResponse(res, 200, true, null, 'Task list — non-named cannot see specific');
        expect(body.data.map((t: any) => t.id)).not.toContain(privateId);

        await adminCtx.delete(`${baseURL}/api/v1/calendar/tasks/${privateId}`);
    });

    test('Task update: invalid update_scope returns 400', async ({ baseURL }) => {
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: { title: 'Scope Validation Task', access_type: 'only_me', rrule: { frequency: 'weekly', interval: 1, until: '2026-12-31' } },
        });
        const scopeTaskId = (await createRes.json()).data.id;

        const payload = { title: 'Bad Scope', update_scope: 'single' };
        const res = await userCtx.put(`${baseURL}/api/v1/calendar/tasks/${scopeTaskId}`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Task update — invalid update_scope');
        expectValidationField(body.error.details, 'update_scope');

        await userCtx.delete(`${baseURL}/api/v1/calendar/tasks/${scopeTaskId}`);
    });

    test('Task update: update_scope=this without occurrence_date returns 400', async ({ baseURL }) => {
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: { title: 'Missing Date Task', access_type: 'only_me', rrule: { frequency: 'weekly', interval: 1, until: '2026-12-31' } },
        });
        const scopeTaskId = (await createRes.json()).data.id;

        const payload = { title: 'No Date', update_scope: 'this' };
        const res = await userCtx.put(`${baseURL}/api/v1/calendar/tasks/${scopeTaskId}`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Task update — this without occurrence_date');
        expectValidationField(body.error.details, 'occurrence_date');

        await userCtx.delete(`${baseURL}/api/v1/calendar/tasks/${scopeTaskId}`);
    });

    test('Recurring task: delete scope=this tombstones one occurrence, parent survives', async ({ baseURL }) => {
        const title = `Delete-Task-Occurrence ${Date.now()}`;
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: {
                title,
                access_type: 'only_me',
                deadline_datetime: '2026-08-07T17:00:00Z',
                rrule: { frequency: 'weekly', interval: 1, by_day: ['FR'], until: '2026-12-31' },
            },
        });
        const recurId = (await createRes.json()).data.id;

        // Delete the 2026-08-14 occurrence
        const deleteRes = await userCtx.delete(
            `${baseURL}/api/v1/calendar/tasks/${recurId}?scope=this&occurrence_date=2026-08-14`,
        );
        const deleteBody = await expectCustomResponse(deleteRes, 200, true, null, 'Recurring task — delete scope=this');
        expect(deleteBody.data.deleted).toBe(true);

        // Parent still accessible
        expect((await userCtx.get(`${baseURL}/api/v1/calendar/tasks/${recurId}`)).status()).toBe(200);

        // Tombstoned occurrence absent from day view
        const dayRes = await userCtx.get(`${baseURL}/api/v1/calendar/day?date=2026-08-14`);
        const dayBody = await expectCustomResponse(dayRes, 200, true, null, 'Recurring task — tombstoned day absent');
        expect(itemsWithTitle(dayBody.data.tasks ?? [], title)).toHaveLength(0);

        // Adjacent occurrence (2026-08-21) still present
        const nextDayRes = await userCtx.get(`${baseURL}/api/v1/calendar/day?date=2026-08-21`);
        const nextDayBody = await expectCustomResponse(nextDayRes, 200, true, null, 'Recurring task — next occurrence present');
        expect(itemsWithTitle(nextDayBody.data.tasks ?? [], title)).toHaveLength(1);

        await userCtx.delete(`${baseURL}/api/v1/calendar/tasks/${recurId}`);
    });

    test('Recurring task: delete scope=this_and_future truncates task series', async ({ baseURL }) => {
        const title = `Delete-Future-Tasks ${Date.now()}`;
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: {
                title,
                access_type: 'only_me',
                deadline_datetime: '2026-08-07T17:00:00Z',
                rrule: { frequency: 'weekly', interval: 1, by_day: ['FR'], until: '2026-12-31' },
            },
        });
        const recurId = (await createRes.json()).data.id;

        // Truncate from 2026-08-21 onwards — 2026-08-14 should remain
        const deleteRes = await userCtx.delete(
            `${baseURL}/api/v1/calendar/tasks/${recurId}?scope=this_and_future&occurrence_date=2026-08-21`,
        );
        await expectCustomResponse(deleteRes, 200, true, null, 'Recurring task — delete this_and_future');

        // 2026-08-14 still present
        const beforeRes = await userCtx.get(`${baseURL}/api/v1/calendar/day?date=2026-08-14`);
        const beforeBody = await expectCustomResponse(beforeRes, 200, true, null, 'Recurring task — occurrence before cut survives');
        expect(itemsWithTitle(beforeBody.data.tasks ?? [], title)).toHaveLength(1);

        // 2026-08-21 (the cut point) is gone
        const cutRes = await userCtx.get(`${baseURL}/api/v1/calendar/day?date=2026-08-21`);
        const cutBody = await expectCustomResponse(cutRes, 200, true, null, 'Recurring task — cut occurrence gone');
        expect(itemsWithTitle(cutBody.data.tasks ?? [], title)).toHaveLength(0);

        await userCtx.delete(`${baseURL}/api/v1/calendar/tasks/${recurId}`);
    });

    test('Recurring task: delete scope=this without occurrence_date returns 400', async ({ baseURL }) => {
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: {
                title: 'Task-Scope-Delete-Validation',
                access_type: 'only_me',
                rrule: { frequency: 'weekly', interval: 1, until: '2026-12-31' },
            },
        });
        const recurId = (await createRes.json()).data.id;

        const res = await userCtx.delete(`${baseURL}/api/v1/calendar/tasks/${recurId}?scope=this`);
        const body = await expectCustomResponse(res, 400, false, null, 'Recurring task — delete scope=this missing occurrence_date');
        expectValidationField(body.error.details, 'occurrence_date');

        await userCtx.delete(`${baseURL}/api/v1/calendar/tasks/${recurId}`);
    });

    test('Task list: status filter', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/tasks/?status=pending`);
        const body = await expectCustomResponse(res, 200, true, null, 'Task list — status filter');
        for (const t of body.data) expect(t.status).toBe('pending');
    });

    test('Task list: priority filter', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/tasks/?priority=high`);
        const body = await expectCustomResponse(res, 200, true, null, 'Task list — priority filter');
        for (const t of body.data) expect(t.priority).toBe('high');
    });

    test('Task list: deadline from_date/to_date filter', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/tasks/?from_date=2026-08-24&to_date=2026-08-26`);
        const body = await expectCustomResponse(res, 200, true, null, 'Task list — deadline filter');
        expect(body.data.map((t: any) => t.id)).toContain(taskIdGroup);
    });

    test('Task list with dates: recurring task appears for occurrences after parent deadline_datetime', async ({ baseURL }) => {
        const title = `Recurring Task Window ${Date.now()}`;
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: {
                title,
                access_type: 'only_me',
                deadline_datetime: '2026-07-31T17:00:00Z',
                rrule: { frequency: 'weekly', interval: 1, by_day: ['FR'], until: '2026-09-30' },
            },
        });
        const createBody = await expectCustomResponse(createRes, 201, true, null, 'Task list — create recurring window task');
        const recurringTaskId = createBody.data.id;

        try {
            const listRes = await userCtx.get(
                `${baseURL}/api/v1/calendar/tasks/?from_date=2026-08-07&to_date=2026-08-21&creator_id=${userId}&page_size=5000`,
            );
            const listBody = await expectCustomResponse(listRes, 200, true, null, 'Task list — recurring summary date window');
            const recurringParent = expectSingleTitledItem(listBody.data, title);
            expect(recurringParent.deadline_datetime).toBe('2026-07-31T17:00:00Z');

            const dayRes = await userCtx.get(`${baseURL}/api/v1/calendar/day?date=2026-08-14`);
            const dayBody = await expectCustomResponse(dayRes, 200, true, null, 'Task list — recurring day detail');
            const expandedTask = expectSingleTitledItem(dayBody.data.tasks, title);
            expect(expandedTask.deadline_datetime).toBe('2026-08-14T17:00:00Z');
        } finally {
            await userCtx.delete(`${baseURL}/api/v1/calendar/tasks/${recurringTaskId}`).catch(() => {});
        }
    });

    // ══════════════════════════════════════════════════════════════════════════
    // SECTION 7 — TASK DETAIL / PATCH DISPATCH
    // ══════════════════════════════════════════════════════════════════════════

    test('Task detail: creator can get task with comments field', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/tasks/${taskIdGroup}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Task detail — creator');
        expect(body.data.id).toBe(taskIdGroup);
        expect(body.data).toHaveProperty('comment_count');
        expect(body.data).toHaveProperty('comments');
    });

    test('Task detail: member gets 404 on only_me task', async ({ baseURL }) => {
        const res = await adminCtx.get(`${baseURL}/api/v1/calendar/tasks/${taskIdOnlyMe}`);
        expect(res.status()).toBe(404);
    });

    test('Task detail: non-existent returns 404', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/tasks/00000000-0000-0000-0000-000000000001`);
        expect(res.status()).toBe(404);
    });

    test('Task PUT /status: member can update status back to pending', async ({ baseURL }) => {
        // Use a fresh task so state doesn't bleed between tests
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: { title: 'Status Test Task', access_type: 'mixed', access_family_ids: [familyId] },
        });
        const statusTaskId = (await createRes.json()).data.id;

        await userCtx.put(`${baseURL}/api/v1/calendar/tasks/${statusTaskId}/status`, { data: { status: 'done' } });

        const res = await adminCtx.put(`${baseURL}/api/v1/calendar/tasks/${statusTaskId}/status`, { data: { status: 'pending' } });
        const body = await expectCustomResponse(res, 200, true, null, 'Task PUT /status — status=pending by member');
        expect(body.data.status).toBe('pending');
        expect(body.data.completed_at).toBeNull();
        expect(body.data.done_by).toBeNull();

        await userCtx.delete(`${baseURL}/api/v1/calendar/tasks/${statusTaskId}`);
    });

    test('Task PUT /status: status → done sets completed_at and done_by', async ({ baseURL }) => {
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: { title: 'Done Test Task', access_type: 'mixed', access_family_ids: [familyId] },
        });
        const doneTaskId = (await createRes.json()).data.id;

        const res = await adminCtx.put(`${baseURL}/api/v1/calendar/tasks/${doneTaskId}/status`, { data: { status: 'done' } });
        const body = await expectCustomResponse(res, 200, true, null, 'Task PUT /status — status=done');
        expect(body.data.status).toBe('done');
        expect(body.data.completed_at).not.toBeNull();
        expect(body.data.done_by).toBe(adminUserId);

        await userCtx.delete(`${baseURL}/api/v1/calendar/tasks/${doneTaskId}`);
    });

    test('Task PUT /status: revert status to pending clears completed_at', async ({ baseURL }) => {
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: { title: 'Revert Test Task', access_type: 'mixed', access_family_ids: [familyId] },
        });
        const revertTaskId = (await createRes.json()).data.id;

        await userCtx.put(`${baseURL}/api/v1/calendar/tasks/${revertTaskId}/status`, { data: { status: 'done' } });

        const res = await userCtx.put(`${baseURL}/api/v1/calendar/tasks/${revertTaskId}/status`, { data: { status: 'pending' } });
        const body = await expectCustomResponse(res, 200, true, null, 'Task PUT /status — revert to pending');
        expect(body.data.status).toBe('pending');
        expect(body.data.completed_at).toBeNull();

        await userCtx.delete(`${baseURL}/api/v1/calendar/tasks/${revertTaskId}`);
    });

    test('Task PUT /status: reject invalid status value', async ({ baseURL }) => {
        const payload = { status: 'archived' };
        const res = await userCtx.put(`${baseURL}/api/v1/calendar/tasks/${taskIdGroup}/status`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Task PUT /status — invalid status');
        expectValidationField(body.error.details, 'status');
    });

    test('Task PATCH: returns 405 Method Not Allowed', async ({ baseURL }) => {
        const res = await userCtx.patch(`${baseURL}/api/v1/calendar/tasks/${taskIdGroup}`, { data: { status: 'done' } });
        expect(res.status()).toBe(405);
    });

    test('Task PUT /status/acknowledge: sets acknowledged_at and is_visible=false', async ({ baseURL }) => {
        // Create a task shared with admin so admin can mark it done
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: { title: 'Acknowledge Me', access_type: 'mixed', access_user_ids: [adminUserId] },
        });
        const ackTaskId = (await createRes.json()).data.id;

        // Admin marks the task done (triggers done_by + completed_at)
        await adminCtx.put(`${baseURL}/api/v1/calendar/tasks/${ackTaskId}/status`, { data: { status: 'done' } });

        // Creator accepts/acknowledges the completion
        const res = await userCtx.put(`${baseURL}/api/v1/calendar/tasks/${ackTaskId}/status/acknowledge`, { data: { action: 'accept' } });
        const body = await expectCustomResponse(res, 200, true, null, 'Task PUT /status/acknowledge — accept');
        expect(body.data.acknowledged_at).not.toBeNull();
        expect(body.data.is_visible).toBe(false);
        // Task is acknowledged (soft-hidden) — no delete needed
    });

    test('Task PUT /status/acknowledge: non-creator gets 403 or 404', async ({ baseURL }) => {
        // Non-creator cannot call the acknowledge endpoint on another user's task
        const res = await adminCtx.put(`${baseURL}/api/v1/calendar/tasks/${taskIdOnlyMe}/status/acknowledge`, { data: { action: 'accept' } });
        expect([403, 404]).toContain(res.status());
    });

    test('Task PUT /status/acknowledge: returns 400 when task is still pending', async ({ baseURL }) => {
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: { title: 'Pending Guard Task', access_type: 'only_me' },
        });
        const pendingTaskId = (await createRes.json()).data.id;

        const res = await userCtx.put(`${baseURL}/api/v1/calendar/tasks/${pendingTaskId}/status/acknowledge`, { data: { action: 'accept' } });
        expect(res.status()).toBe(400);

        await userCtx.delete(`${baseURL}/api/v1/calendar/tasks/${pendingTaskId}`);
    });

    test('Task PUT /status/acknowledge: returns 400 when already acknowledged', async ({ baseURL }) => {
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: { title: 'Double Ack Task', access_type: 'mixed', access_user_ids: [adminUserId] },
        });
        const doubleAckTaskId = (await createRes.json()).data.id;

        await adminCtx.put(`${baseURL}/api/v1/calendar/tasks/${doubleAckTaskId}/status`, { data: { status: 'done' } });
        await userCtx.put(`${baseURL}/api/v1/calendar/tasks/${doubleAckTaskId}/status/acknowledge`, { data: { action: 'accept' } });

        // Second acknowledge call should return 400
        const res = await userCtx.put(`${baseURL}/api/v1/calendar/tasks/${doubleAckTaskId}/status/acknowledge`, { data: { action: 'accept' } });
        expect(res.status()).toBe(400);
    });

    test('Task PUT: creator can do full update', async ({ baseURL }) => {
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: { title: 'PUT Test Task', access_type: 'only_me' },
        });
        const putTaskId = (await createRes.json()).data.id;

        const payload = { title: 'Updated via PUT', priority: 'medium' };
        const res = await userCtx.put(`${baseURL}/api/v1/calendar/tasks/${putTaskId}`, { data: payload });
        const body = await expectCustomResponse(res, 200, true, payload, 'Task PUT — full update');
        expect(body.data.title).toBe('Updated via PUT');

        await userCtx.delete(`${baseURL}/api/v1/calendar/tasks/${putTaskId}`);
    });

    test('Task delete: creator can delete, task gone after', async ({ baseURL }) => {
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: { title: 'Delete Me Task', access_type: 'only_me' },
        });
        const deleteTaskId = (await createRes.json()).data.id;

        const res = await userCtx.delete(`${baseURL}/api/v1/calendar/tasks/${deleteTaskId}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Task delete — creator');
        expect(body.data.deleted).toBe(true);

        expect((await userCtx.get(`${baseURL}/api/v1/calendar/tasks/${deleteTaskId}`)).status()).toBe(404);
    });

    test('Task delete: non-creator gets 403 or 404', async ({ baseURL }) => {
        const res = await adminCtx.delete(`${baseURL}/api/v1/calendar/tasks/${taskIdOnlyMe}`);
        expect([403, 404]).toContain(res.status());
    });

    // ══════════════════════════════════════════════════════════════════════════
    // SECTION 8 — EVENT COMMENTS (nested endpoints)
    // ══════════════════════════════════════════════════════════════════════════

    test('Event comments: creator can add comment', async ({ baseURL }) => {
        const payload = { comment: 'This will be a great dinner!' };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/events/${eventIdGroup}/comments`, { data: payload });
        const body = await expectCustomResponse(res, 201, true, payload, 'Event comment — creator adds');
        eventCommentId = body.data.id;
        expect(body.data.comment).toBe('This will be a great dinner!');
        expect(body.data.parent_type).toBe('event');
        expect(body.data.parent_id).toBe(eventIdGroup);

        const detailRes = await userCtx.get(`${baseURL}/api/v1/calendar/events/${eventIdGroup}`);
        const detailBody = await expectCustomResponse(detailRes, 200, true, null, 'Event detail — comment_count after add');
        expect(detailBody.data.comment_count).toBe(1);
    });

    test('Event comments: family member can add comment', async ({ baseURL }) => {
        const payload = { comment: 'I will bring dessert!' };
        const res = await adminCtx.post(`${baseURL}/api/v1/calendar/events/${eventIdGroup}/comments`, { data: payload });
        const body = await expectCustomResponse(res, 201, true, payload, 'Event comment — member adds');
        expect(body.data.comment).toBe('I will bring dessert!');
    });

    test('Event comments: creator can list comments', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/events/${eventIdGroup}/comments`);
        const body = await expectCustomResponse(res, 200, true, null, 'Event comments — list');
        expect(Array.isArray(body.data)).toBe(true);
        expect(body.data.length).toBeGreaterThanOrEqual(1);
        expect(body.data.map((c: any) => c.id)).toContain(eventCommentId);
    });

    test('Event comments: member can list comments on group event', async ({ baseURL }) => {
        const res = await adminCtx.get(`${baseURL}/api/v1/calendar/events/${eventIdGroup}/comments`);
        const body = await expectCustomResponse(res, 200, true, null, 'Event comments — member lists');
        expect(Array.isArray(body.data)).toBe(true);
    });

    test('Event comments: non-access user gets 404 on only_me event', async ({ baseURL }) => {
        const payload = { comment: 'I should not be here' };
        await logRequestPayload('POST', `${baseURL}/api/v1/calendar/events/${eventIdOnlyMe}/comments`, payload, 'Event comment — non-access');
        const res = await adminCtx.post(`${baseURL}/api/v1/calendar/events/${eventIdOnlyMe}/comments`, { data: payload });
        expect(res.status()).toBe(404);
    });

    test('Event comments: reject empty comment', async ({ baseURL }) => {
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/events/${eventIdGroup}/comments`, { data: { comment: '' } });
        const body = await res.json();
        await attachResponseToReport(body, 'Event comment — empty comment');
        expect(res.status()).toBe(400);
    });

    test('Event comments: owner can delete own comment', async ({ baseURL }) => {
        const res = await userCtx.delete(`${baseURL}/api/v1/calendar/comments/${eventCommentId}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Event comment — owner deletes');
        expect(body.data.deleted).toBe(true);

        const detailRes = await userCtx.get(`${baseURL}/api/v1/calendar/events/${eventIdGroup}`);
        const detailBody = await expectCustomResponse(detailRes, 200, true, null, 'Event detail — comment_count after delete');
        expect(detailBody.data.comment_count).toBe(1);
    });

    test('Event comments: non-owner cannot delete others comment (403)', async ({ baseURL }) => {
        const addRes = await adminCtx.post(`${baseURL}/api/v1/calendar/events/${eventIdGroup}/comments`, {
            data: { comment: 'Admin comment to protect' },
        });
        const adminCommentId = (await addRes.json()).data.id;

        await logRequestPayload('DELETE', `${baseURL}/api/v1/calendar/comments/${adminCommentId}`, null, 'Event comment — non-owner delete');
        const res = await userCtx.delete(`${baseURL}/api/v1/calendar/comments/${adminCommentId}`);
        expect(res.status()).toBe(403);

        await adminCtx.delete(`${baseURL}/api/v1/calendar/comments/${adminCommentId}`);
    });

    test('Event comments: delete non-existent comment returns 404', async ({ baseURL }) => {
        const res = await userCtx.delete(`${baseURL}/api/v1/calendar/comments/00000000-0000-0000-0000-000000000002`);
        expect(res.status()).toBe(404);
    });

    test('Event comments: recurring occurrence comment creates override with comment_count', async ({ baseURL }) => {
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
            data: {
                title: 'Recurring Event Comments',
                start_at: '2026-10-05T09:00:00Z',
                access_type: 'only_me',
                rrule: { frequency: 'weekly', interval: 1, by_day: ['MO'], until: '2026-11-30' },
            },
        });
        const recurId = (await createRes.json()).data.id;

        const payload = { comment: 'Occurrence-specific event note', occurrence_date: '2026-10-19' };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/events/${recurId}/comments`, { data: payload });
        const body = await expectCustomResponse(res, 201, true, payload, 'Event comment — recurring occurrence');
        expect(body.data.parent_id).not.toBe(recurId);

        const listRes = await userCtx.get(`${baseURL}/api/v1/calendar/events/${recurId}/comments?occurrence_date=2026-10-19`);
        const listBody = await expectCustomResponse(listRes, 200, true, null, 'Event comments — recurring occurrence list');
        expect(listBody.data.map((comment: any) => comment.id)).toContain(body.data.id);

        const dayRes = await userCtx.get(`${baseURL}/api/v1/calendar/day?date=2026-10-19`);
        const dayBody = await expectCustomResponse(dayRes, 200, true, null, 'Event comments — recurring occurrence day');
        const override = (dayBody.data.events ?? []).find((event: any) => event.parent_event_id === recurId);
        expect(override).toBeDefined();
        expect(override.comment_count).toBe(1);
        expect((override.comments ?? []).map((comment: any) => comment.id)).toContain(body.data.id);

        await userCtx.delete(`${baseURL}/api/v1/calendar/events/${recurId}`).catch(() => {});
    });

    test('Event comments: unauthenticated list request rejected', async ({ request, baseURL }) => {
        const res = await request.get(`${baseURL}/api/v1/calendar/events/${eventIdGroup}/comments`);
        expect([401, 403]).toContain(res.status());
    });

    // ══════════════════════════════════════════════════════════════════════════
    // SECTION 9 — TASK COMMENTS (nested endpoints)
    // ══════════════════════════════════════════════════════════════════════════

    test('Task comments: creator can add comment', async ({ baseURL }) => {
        const payload = { comment: 'Will pay by end of day' };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/tasks/${taskIdGroup}/comments`, { data: payload });
        const body = await expectCustomResponse(res, 201, true, payload, 'Task comment — creator adds');
        taskCommentId = body.data.id;
        expect(body.data.parent_type).toBe('task');
        expect(body.data.parent_id).toBe(taskIdGroup);

        const detailRes = await userCtx.get(`${baseURL}/api/v1/calendar/tasks/${taskIdGroup}`);
        const detailBody = await expectCustomResponse(detailRes, 200, true, null, 'Task detail — comment_count after add');
        expect(detailBody.data.comment_count).toBe(1);
    });

    test('Task comments: member can add comment on group task', async ({ baseURL }) => {
        const payload = { comment: 'I can also help!' };
        const res = await adminCtx.post(`${baseURL}/api/v1/calendar/tasks/${taskIdGroup}/comments`, { data: payload });
        const body = await expectCustomResponse(res, 201, true, payload, 'Task comment — member adds');
        expect(body.data.comment).toBe('I can also help!');
    });

    test('Task comments: creator can list comments', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/tasks/${taskIdGroup}/comments`);
        const body = await expectCustomResponse(res, 200, true, null, 'Task comments — list');
        expect(Array.isArray(body.data)).toBe(true);
        expect(body.data.length).toBeGreaterThanOrEqual(1);
    });

    test('Task comments: non-access user gets 404 on only_me task', async ({ baseURL }) => {
        const res = await adminCtx.post(`${baseURL}/api/v1/calendar/tasks/${taskIdOnlyMe}/comments`, { data: { comment: 'Trespassing' } });
        expect(res.status()).toBe(404);
    });

    test('Task comments: owner can delete own comment', async ({ baseURL }) => {
        const res = await userCtx.delete(`${baseURL}/api/v1/calendar/comments/${taskCommentId}`);
        const body = await expectCustomResponse(res, 200, true, null, 'Task comment — owner deletes');
        expect(body.data.deleted).toBe(true);

        const detailRes = await userCtx.get(`${baseURL}/api/v1/calendar/tasks/${taskIdGroup}`);
        const detailBody = await expectCustomResponse(detailRes, 200, true, null, 'Task detail — comment_count after delete');
        expect(detailBody.data.comment_count).toBe(1);
    });

    test('Task comments: recurring occurrence comment creates override with comment_count', async ({ baseURL }) => {
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: {
                title: 'Recurring Task Comments',
                access_type: 'only_me',
                deadline_datetime: '2026-10-09T17:00:00Z',
                rrule: { frequency: 'weekly', interval: 1, by_day: ['FR'], until: '2026-11-30' },
            },
        });
        const recurId = (await createRes.json()).data.id;

        const payload = { comment: 'Occurrence-specific task note', occurrence_date: '2026-10-23' };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/tasks/${recurId}/comments`, { data: payload });
        const body = await expectCustomResponse(res, 201, true, payload, 'Task comment — recurring occurrence');
        expect(body.data.parent_id).not.toBe(recurId);

        const listRes = await userCtx.get(`${baseURL}/api/v1/calendar/tasks/${recurId}/comments?occurrence_date=2026-10-23`);
        const listBody = await expectCustomResponse(listRes, 200, true, null, 'Task comments — recurring occurrence list');
        expect(listBody.data.map((comment: any) => comment.id)).toContain(body.data.id);

        const dayRes = await userCtx.get(`${baseURL}/api/v1/calendar/day?date=2026-10-23`);
        const dayBody = await expectCustomResponse(dayRes, 200, true, null, 'Task comments — recurring occurrence day');
        const override = (dayBody.data.tasks ?? []).find((task: any) => task.parent_task_id === recurId);
        expect(override).toBeDefined();
        expect(override.comment_count).toBe(1);
        expect((override.comments ?? []).map((comment: any) => comment.id)).toContain(body.data.id);

        await userCtx.delete(`${baseURL}/api/v1/calendar/tasks/${recurId}`).catch(() => {});
    });

    // ══════════════════════════════════════════════════════════════════════════
    // SECTION 10 — UNIFIED CALENDAR VIEW
    // ══════════════════════════════════════════════════════════════════════════

    test('Unified calendar: GET with valid dates returns events + tasks + general_events', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/?from_date=2026-08-01&to_date=2026-08-31`);
        const body = await expectCustomResponse(res, 200, true, null, 'Unified calendar — GET structure');
        expect(body.data).toHaveProperty('events');
        expect(body.data).toHaveProperty('general_events');
        expect(body.data).toHaveProperty('tasks');
        expect(Array.isArray(body.data.events)).toBe(true);
        expect(Array.isArray(body.data.general_events)).toBe(true);
        expect(Array.isArray(body.data.tasks)).toBe(true);

        expect((body.data.events ?? []).length).toBeGreaterThan(0);
        expect((body.data.tasks ?? []).length).toBeGreaterThan(0);
        const eventItem = body.data.events[0];
        const taskItem = body.data.tasks[0];
        expect(eventItem).toBeDefined();
        expect(eventItem).toHaveProperty('id');
        expect(eventItem).toHaveProperty('title');
        expect(eventItem).toHaveProperty('start_at');
        expect(eventItem).toHaveProperty('all_day');
        expect(eventItem).toHaveProperty('rrule');
        expect(eventItem).not.toHaveProperty('description');
        expect(eventItem).not.toHaveProperty('comments');
        expect(taskItem).toBeDefined();
        expect(taskItem).toHaveProperty('id');
        expect(taskItem).toHaveProperty('title');
        expect(taskItem).toHaveProperty('deadline_datetime');
        expect(taskItem).toHaveProperty('priority');
        expect(taskItem).toHaveProperty('status');
        expect(taskItem).not.toHaveProperty('description');
        expect(taskItem).not.toHaveProperty('comments');
        expect(body.meta).toBeNull();
    });

    test('Unified calendar: rejects date windows longer than 31 days', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/?from_date=2026-08-01&to_date=2026-09-01`);
        const body = await expectCustomResponse(res, 400, false, null, 'Unified calendar — 31 day cap GET');
        expectValidationField(body.error.details, 'to_date', '31 days');
    });

    test('Unified calendar: missing dates returns 400', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar`);
        const body = await res.json();
        await attachResponseToReport(body, 'Unified calendar — no dates');
        expect(res.status()).toBe(400);
        expectValidationField(body.error.details, 'from_date');
        expectValidationField(body.error.details, 'to_date');
    });

    test('Unified calendar: access control hides only_me events from member', async ({ baseURL }) => {
        const res = await adminCtx.get(`${baseURL}/api/v1/calendar/?from_date=2026-08-01&to_date=2026-08-31`);
        const body = await expectCustomResponse(res, 200, true, null, 'Unified calendar — access control');
        const allIds = (body.data.events ?? []).map((e: any) => e.id);
        expect(allIds).not.toContain(eventIdOnlyMe);
    });

    test('Unified calendar: unauthenticated request rejected', async ({ request, baseURL }) => {
        const res = await request.get(`${baseURL}/api/v1/calendar/?from_date=2026-08-01&to_date=2026-08-31`);
        expect([401, 403]).toContain(res.status());
    });

    test('Calendar day: GET returns full details for one exact date', async ({ baseURL }) => {
        const suffix = Date.now();
        const eventTitle = `Calendar Day Event ${suffix}`;
        const taskTitle = `Calendar Day Task ${suffix}`;

        const eventRes = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
            data: {
                title: eventTitle,
                description: 'Detailed event payload',
                start_at: '2026-11-03T10:00:00Z',
                access_type: 'only_me',
            },
        });
        const eventBody = await expectCustomResponse(eventRes, 201, true, null, 'Calendar day — create event');

        const taskRes = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: {
                title: taskTitle,
                description: 'Detailed task payload',
                access_type: 'only_me',
                priority: 'high',
                deadline_datetime: '2026-11-03T12:00:00Z',
            },
        });
        const taskBody = await expectCustomResponse(taskRes, 201, true, null, 'Calendar day — create task');

        try {
            const res = await userCtx.get(`${baseURL}/api/v1/calendar/day?date=2026-11-03`);
            const body = await expectCustomResponse(res, 200, true, null, 'Calendar day — full details');
            expect(body.data.date).toBe('2026-11-03');
            expect(body.data).toHaveProperty('events');
            expect(body.data).toHaveProperty('tasks');

            const eventItem = (body.data.events as any[]).find((item: any) => item.id === eventBody.data.id);
            const taskItem = (body.data.tasks as any[]).find((item: any) => item.id === taskBody.data.id);

            expect(eventItem).toBeDefined();
            expect(eventItem.description).toBe('Detailed event payload');
            expect(eventItem).toHaveProperty('access_type');
            expect(eventItem).toHaveProperty('comment_count');
            expect(eventItem).toHaveProperty('comments');

            expect(taskItem).toBeDefined();
            expect(taskItem.description).toBe('Detailed task payload');
            expect(taskItem.priority).toBe('high');
            expect(taskItem).toHaveProperty('access_type');
            expect(taskItem).toHaveProperty('comment_count');
            expect(taskItem).toHaveProperty('comments');
        } finally {
            await userCtx.delete(`${baseURL}/api/v1/calendar/events/${eventBody.data.id}`).catch(() => {});
            await userCtx.delete(`${baseURL}/api/v1/calendar/tasks/${taskBody.data.id}`).catch(() => {});
        }
    });

    test('Calendar day: missing date returns 400', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/day`);
        const body = await res.json();
        expect(res.status()).toBe(400);
        expectValidationField(body.error.details, 'date');
    });

    // ══════════════════════════════════════════════════════════════════════════
    // SECTION 11 — AUTH GUARD
    // ══════════════════════════════════════════════════════════════════════════

    test('Auth guard: GET /calendar/events/ requires auth', async ({ request, baseURL }) => {
        const res = await request.get(`${baseURL}/api/v1/calendar/events`);
        expect([401, 403]).toContain(res.status());
    });

    test('Auth guard: GET /calendar/tasks/ requires auth', async ({ request, baseURL }) => {
        const res = await request.get(`${baseURL}/api/v1/calendar/tasks`);
        expect([401, 403]).toContain(res.status());
    });

    test('Auth guard: GET /calendar/ requires auth', async ({ request, baseURL }) => {
        const res = await request.get(`${baseURL}/api/v1/calendar/?from_date=2026-08-01&to_date=2026-08-31`);
        expect([401, 403]).toContain(res.status());
    });

    test('Auth guard: GET /calendar/day requires auth', async ({ request, baseURL }) => {
        const res = await request.get(`${baseURL}/api/v1/calendar/day?date=2026-08-10`);
        expect([401, 403]).toContain(res.status());
    });

    // ══════════════════════════════════════════════════════════════════════════
    // SECTION 12 — RECURRENCE ENGINE: summaries collapse to parents, day view expands the selected date
    // ══════════════════════════════════════════════════════════════════════════

    test('Event list with dates: recurring parent appears once when a later occurrence overlaps the window', async ({ baseURL }) => {
        const beforeRes = await userCtx.get(
            `${baseURL}/api/v1/calendar/events/?from_date=2026-08-01&to_date=2026-08-31&creator_id=${userId}&page_size=1`,
        );
        const beforeTotal: number = (await beforeRes.json()).meta.total;

        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
            data: {
                title: 'F11-Recur-Test',
                start_at: '2026-07-07T09:00:00Z',
                access_type: 'only_me',
                rrule: { frequency: 'weekly', interval: 1, by_day: ['MO'], until: '2026-12-31' },
            },
        });
        const body = await expectCustomResponse(createRes, 201, true, null, 'F11 — create recurring event');
        const recurId = body.data.id;

        const afterRes = await userCtx.get(
            `${baseURL}/api/v1/calendar/events/?from_date=2026-08-01&to_date=2026-08-31&creator_id=${userId}&page_size=5000`,
        );
        const afterBody = await expectCustomResponse(afterRes, 200, true, null, 'F11 — collapsed recurring summary');
        const matches = itemsWithTitle(afterBody.data, 'F11-Recur-Test');

        expect(afterBody.meta.total).toBe(beforeTotal + 1);
        expect(matches).toHaveLength(1);
        expect(matches[0].start_at).toBe('2026-07-07T09:00:00Z');
        expect(matches[0].rrule?.frequency).toBe('weekly');

        await userCtx.delete(`${baseURL}/api/v1/calendar/events/${recurId}`).catch(() => {});
    });

    test('Event list summaries collapse recurring parents for multiple recurrence frequencies', async ({ baseURL }) => {
        const cases = [
            {
                title: `MWF Family Sync ${Date.now()}`,
                start_at: '2026-08-03T09:00:00Z',
                rrule: { frequency: 'weekly', interval: 1, by_day: ['MO', 'TU', 'WE'], until: '2026-08-12' },
                query: `${baseURL}/api/v1/calendar/events/?from_date=2026-08-03&to_date=2026-08-12&creator_id=${userId}&page_size=5000`,
            },
            {
                title: `Monthly Rent Review ${Date.now()}`,
                start_at: '2026-06-15T09:00:00Z',
                rrule: { frequency: 'monthly', interval: 1, by_month_day: [15], until: '2026-09-30' },
                query: `${baseURL}/api/v1/calendar/events/?from_date=2026-06-15&to_date=2026-09-30&creator_id=${userId}&page_size=5000`,
            },
            {
                title: `Annual Policy Review ${Date.now()}`,
                start_at: '2026-06-10T09:00:00Z',
                rrule: { frequency: 'yearly', interval: 1, until: '2028-12-31' },
                query: `${baseURL}/api/v1/calendar/events/?from_date=2026-06-01&to_date=2026-07-31&creator_id=${userId}&page_size=5000`,
            },
        ];

        const createdIds: string[] = [];

        try {
            for (const item of cases) {
                const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
                    data: {
                        title: item.title,
                        start_at: item.start_at,
                        access_type: 'only_me',
                        rrule: item.rrule,
                    },
                });
                createdIds.push((await createRes.json()).data.id);

                const listRes = await userCtx.get(item.query);
                const listBody = await expectCustomResponse(listRes, 200, true, null, `Recurring summary — ${item.title}`);
                expect(itemsWithTitle(listBody.data, item.title)).toHaveLength(1);
            }
        } finally {
            for (const itemId of createdIds) {
                await userCtx.delete(`${baseURL}/api/v1/calendar/events/${itemId}`).catch(() => {});
            }
        }
    });

    test('Recurring summaries collapse to one parent row and calendar day expands the selected occurrence', async ({ baseURL }) => {
        const title = `Daily Rehab Session ${Date.now()}`;
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
            data: {
                title,
                start_at: '2026-06-01T09:00:00Z',
                access_type: 'only_me',
                rrule: { frequency: 'daily', interval: 1, until: '2026-12-01' },
            },
        });
        const recurId = (await createRes.json()).data.id;

        const listRes = await userCtx.get(
            `${baseURL}/api/v1/calendar/events/?from_date=2026-06-15&to_date=2026-07-15&creator_id=${userId}&page_size=5000`,
        );
        const listBody = await expectCustomResponse(listRes, 200, true, null, 'Recurring summary — daily June range');
        const parentListItem = expectSingleTitledItem(listBody.data, title);
        expect(parentListItem.start_at).toBe('2026-06-01T09:00:00Z');

        const unifiedRes = await userCtx.get(
            `${baseURL}/api/v1/calendar/?from_date=2026-06-15&to_date=2026-07-15`,
        );
        const unifiedBody = await expectCustomResponse(unifiedRes, 200, true, null, 'Recurring summary — daily June unified range');
        expect(itemsWithTitle(unifiedBody.data.events ?? [], title)).toHaveLength(1);

        const dayRes = await userCtx.get(`${baseURL}/api/v1/calendar/day?date=2026-06-20`);
        const dayBody = await expectCustomResponse(dayRes, 200, true, null, 'Recurring day detail — daily June');
        const dayOccurrence = expectSingleTitledItem(dayBody.data.events ?? [], title);
        expect(dayOccurrence.start_at).toBe('2026-06-20T09:00:00Z');

        await userCtx.delete(`${baseURL}/api/v1/calendar/events/${recurId}`).catch(() => {});
    });

    test('Event list with dates: recurrence_end_date respected for collapsed summaries', async ({ baseURL }) => {
        const title = `Ended Daily Medication ${Date.now()}`;
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
            data: {
                title,
                start_at: '2026-06-01T09:00:00Z',
                access_type: 'only_me',
                rrule: { frequency: 'daily', interval: 1, until: '2026-06-30' },
            },
        });
        const recurId = (await createRes.json()).data.id;

        const listRes = await userCtx.get(
            `${baseURL}/api/v1/calendar/events/?from_date=2026-07-01&to_date=2026-07-31&creator_id=${userId}&page_size=5000`,
        );
        const listBody = await expectCustomResponse(listRes, 200, true, null, 'Recurring summary — recurrence_end_date respected');
        expect(itemsWithTitle(listBody.data, title)).toEqual([]);

        await userCtx.delete(`${baseURL}/api/v1/calendar/events/${recurId}`).catch(() => {});
    });

    test('Calendar day: recurring overnight event preserves shifted duration in end_at', async ({ baseURL }) => {
        const title = `Overnight Recurring Event ${Date.now()}`;
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
            data: {
                title,
                start_at: '2026-08-03T23:00:00Z',
                end_at: '2026-08-04T01:00:00Z',
                access_type: 'only_me',
                rrule: { frequency: 'weekly', interval: 1, by_day: ['MO'], until: '2026-08-31' },
            },
        });
        const createBody = await expectCustomResponse(createRes, 201, true, null, 'Recurring — create overnight event');

        try {
            const dayRes = await userCtx.get(`${baseURL}/api/v1/calendar/day?date=2026-08-10`);
            const dayBody = await expectCustomResponse(dayRes, 200, true, null, 'Recurring day detail — overnight duration preserved');
            const occurrence = (dayBody.data.events as any[]).find((item: any) => item.title === title);

            expect(occurrence).toBeDefined();
            expect(occurrence.start_at).toBe('2026-08-10T23:00:00Z');
            expect(occurrence.end_at).toBe('2026-08-11T01:00:00Z');
        } finally {
            await userCtx.delete(`${baseURL}/api/v1/calendar/events/${createBody.data.id}`).catch(() => {});
        }
    });

    test('Event list without dates: returns events without recurrence expansion (DB query path)', async ({ baseURL }) => {
        // Without from_date/to_date the view falls back to the DB query path.
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/events`);
        const body = await expectCustomResponse(res, 200, true, null, 'F11 — no-date-filter path');
        expect(body.meta).toHaveProperty('total');
        expect(Array.isArray(body.data)).toBe(true);
    });

    test('Event list: from_date and to_date filters work independently', async ({ baseURL }) => {
        const suffix = Date.now();
        const earlyTitle = `Event Filter Early ${suffix}`;
        const lateTitle = `Event Filter Late ${suffix}`;

        const earlyRes = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
            data: { title: earlyTitle, start_at: '2026-11-02T09:00:00Z', access_type: 'only_me' },
        });
        const earlyBody = await expectCustomResponse(earlyRes, 201, true, null, 'Event list — create early date filter event');

        const lateRes = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
            data: { title: lateTitle, start_at: '2026-11-05T09:00:00Z', access_type: 'only_me' },
        });
        const lateBody = await expectCustomResponse(lateRes, 201, true, null, 'Event list — create late date filter event');

        try {
            const fromRes = await userCtx.get(
                `${baseURL}/api/v1/calendar/events/?from_date=2026-11-04&creator_id=${userId}&page_size=5000`,
            );
            const fromBody = await expectCustomResponse(fromRes, 200, true, null, 'Event list — from_date only filter');
            const fromTitles = (fromBody.data as any[])
                .filter((item: any) => [earlyTitle, lateTitle].includes(item.title))
                .map((item: any) => item.title);
            expect(fromTitles).toEqual([lateTitle]);

            const toRes = await userCtx.get(
                `${baseURL}/api/v1/calendar/events/?to_date=2026-11-03&creator_id=${userId}&page_size=5000`,
            );
            const toBody = await expectCustomResponse(toRes, 200, true, null, 'Event list — to_date only filter');
            const toTitles = (toBody.data as any[])
                .filter((item: any) => [earlyTitle, lateTitle].includes(item.title))
                .map((item: any) => item.title);
            expect(toTitles).toEqual([earlyTitle]);
        } finally {
            await userCtx.delete(`${baseURL}/api/v1/calendar/events/${earlyBody.data.id}`).catch(() => {});
            await userCtx.delete(`${baseURL}/api/v1/calendar/events/${lateBody.data.id}`).catch(() => {});
        }
    });

    // ══════════════════════════════════════════════════════════════════════════
    // SECTION 13 — RECURRENCE SCOPE HELPER (consolidated from 3 duplicates)
    // These tests exercise the shared _validate_recurrence_scope path via both
    // EventDetailView.put and TaskDetailView.put/patch.
    // ══════════════════════════════════════════════════════════════════════════

    test('Scope helper: Event PUT — bad scope returns update_scope error key', async ({ baseURL }) => {
        const payload = { title: 'Bad Scope Event', update_scope: 'invalid' };
        const res = await userCtx.put(`${baseURL}/api/v1/calendar/events/${eventIdRecurring}`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Scope helper — event PUT bad scope');
        expectValidationField(body.error.details, 'update_scope');
    });

    test('Scope helper: Task PUT — bad scope returns update_scope error key', async ({ baseURL }) => {
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: { title: 'Scope Helper Task', access_type: 'only_me',
                    rrule: { frequency: 'weekly', interval: 1, until: '2026-12-31' } },
        });
        const scopeId = (await createRes.json()).data.id;
        const payload = { title: 'New Title', update_scope: 'invalid' };
        const res = await userCtx.put(`${baseURL}/api/v1/calendar/tasks/${scopeId}`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Scope helper — task PUT bad scope');
        expectValidationField(body.error.details, 'update_scope');
        await userCtx.delete(`${baseURL}/api/v1/calendar/tasks/${scopeId}`).catch(() => {});
    });

    test('Scope helper: Task PATCH (general) — bad scope returns update_scope error key', async ({ baseURL }) => {
        const createRes = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: { title: 'Scope Helper Patch Task', access_type: 'only_me',
                    rrule: { frequency: 'weekly', interval: 1, until: '2026-12-31' } },
        });
        const scopeId = (await createRes.json()).data.id;
        const payload = { title: 'New Title', update_scope: 'oops' };
        const res = await userCtx.patch(`${baseURL}/api/v1/calendar/tasks/${scopeId}`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Scope helper — task PATCH bad scope');
        expectValidationField(body.error.details, 'update_scope');
        await userCtx.delete(`${baseURL}/api/v1/calendar/tasks/${scopeId}`).catch(() => {});
    });

    // ══════════════════════════════════════════════════════════════════════════
    // SECTION 14 — ACCESS FIELDS SHARED VALIDATOR
    // Both EventWriteSerializer and TaskWriteSerializer now use the shared
    // validate_access_fields() function.  Verify both still enforce the same rules.
    // ══════════════════════════════════════════════════════════════════════════

    test('Shared validator: Event — mixed with all empty targets rejected', async ({ baseURL }) => {
        const payload = {
            title: 'Bad Group Event', start_at: '2026-09-01T10:00:00Z',
            access_type: 'mixed', access_family_ids: [], access_close_group_ids: [], access_user_ids: [],
        };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/events`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Shared validator — event mixed no target');
        expectValidationField(body.error.details, 'access_type');
    });

    test('Shared validator: Task — mixed with all empty targets rejected', async ({ baseURL }) => {
        const payload = {
            title: 'Bad Group Task',
            access_type: 'mixed', access_family_ids: [], access_close_group_ids: [], access_user_ids: [],
        };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Shared validator — task mixed no target');
        expectValidationField(body.error.details, 'access_type');
    });

    test('Shared validator: Event — mixed with empty access_user_ids only rejected', async ({ baseURL }) => {
        const payload = {
            title: 'Bad Specific Event', start_at: '2026-09-01T10:00:00Z',
            access_type: 'mixed', access_family_ids: [], access_close_group_ids: [], access_user_ids: [],
        };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/events`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Shared validator — event mixed empty users');
        expectValidationField(body.error.details, 'access_type');
    });

    test('Shared validator: Task — mixed with empty access_user_ids only rejected', async ({ baseURL }) => {
        const payload = { title: 'Bad Specific Task', access_type: 'mixed', access_family_ids: [], access_close_group_ids: [], access_user_ids: [] };
        const res = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, { data: payload });
        const body = await expectCustomResponse(res, 400, false, payload, 'Shared validator — task mixed empty users');
        expectValidationField(body.error.details, 'access_type');
    });

    // ══════════════════════════════════════════════════════════════════════════
    // SECTION 15 — CALENDAR SERVICE SEAM (serialization in view, not service)
    // The unified calendar view serializes the raw lists returned by CalendarService.
    // Verify the response shape is identical to before the refactor.
    // ══════════════════════════════════════════════════════════════════════════

    test('Unified calendar: response still has events and tasks keys after service refactor', async ({ baseURL }) => {
        const res = await userCtx.get(`${baseURL}/api/v1/calendar/?from_date=2026-08-01&to_date=2026-08-31`);
        const body = await expectCustomResponse(res, 200, true, null, 'CalendarService seam — shape preserved');
        expect(body.data).toHaveProperty('events');
        expect(body.data).toHaveProperty('general_events');
        expect(body.data).toHaveProperty('tasks');
        expect(body.data).toHaveProperty('from_date');
        expect(body.data).toHaveProperty('to_date');
        expect(Array.isArray(body.data.events)).toBe(true);
        expect(Array.isArray(body.data.tasks)).toBe(true);
    });

    test('Date-window calendar APIs order items by their actual datetime, not creation order', async ({ baseURL }) => {
        const suffix = Date.now();
        const eventEarlierTitle = `Chrono Event Earlier ${suffix}`;
        const eventLaterTitle = `Chrono Event Later ${suffix}`;
        const taskEarlierTitle = `Chrono Task Earlier ${suffix}`;
        const taskLaterTitle = `Chrono Task Later ${suffix}`;

        const eventLaterRes = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
            data: { title: eventLaterTitle, start_at: '2026-11-10T15:00:00Z', access_type: 'only_me' },
        });
        const eventLaterBody = await expectCustomResponse(eventLaterRes, 201, true, null, 'Chrono order — create later event');

        const eventEarlierRes = await userCtx.post(`${baseURL}/api/v1/calendar/events`, {
            data: { title: eventEarlierTitle, start_at: '2026-11-10T09:00:00Z', access_type: 'only_me' },
        });
        const eventEarlierBody = await expectCustomResponse(eventEarlierRes, 201, true, null, 'Chrono order — create earlier event');

        const taskLaterRes = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: { title: taskLaterTitle, access_type: 'only_me', deadline_datetime: '2026-11-10T18:00:00Z' },
        });
        const taskLaterBody = await expectCustomResponse(taskLaterRes, 201, true, null, 'Chrono order — create later task');

        const taskEarlierRes = await userCtx.post(`${baseURL}/api/v1/calendar/tasks`, {
            data: { title: taskEarlierTitle, access_type: 'only_me', deadline_datetime: '2026-11-10T08:00:00Z' },
        });
        const taskEarlierBody = await expectCustomResponse(taskEarlierRes, 201, true, null, 'Chrono order — create earlier task');

        try {
            const eventListRes = await userCtx.get(
                `${baseURL}/api/v1/calendar/events/?from_date=2026-11-10&to_date=2026-11-10&creator_id=${userId}&page_size=5000`,
            );
            const eventListBody = await expectCustomResponse(eventListRes, 200, true, null, 'Chrono order — event list');
            const eventTitles = (eventListBody.data as any[])
                .filter((item: any) => [eventEarlierTitle, eventLaterTitle].includes(item.title))
                .map((item: any) => item.title);
            expect(eventTitles).toEqual([eventEarlierTitle, eventLaterTitle]);

            const taskListRes = await userCtx.get(
                `${baseURL}/api/v1/calendar/tasks/?from_date=2026-11-10&to_date=2026-11-10&creator_id=${userId}&page_size=5000`,
            );
            const taskListBody = await expectCustomResponse(taskListRes, 200, true, null, 'Chrono order — task list');
            const taskTitles = (taskListBody.data as any[])
                .filter((item: any) => [taskEarlierTitle, taskLaterTitle].includes(item.title))
                .map((item: any) => item.title);
            expect(taskTitles).toEqual([taskEarlierTitle, taskLaterTitle]);

            const unifiedRes = await userCtx.get(`${baseURL}/api/v1/calendar/?from_date=2026-11-10&to_date=2026-11-10`);
            const unifiedBody = await expectCustomResponse(unifiedRes, 200, true, null, 'Chrono order — unified calendar');

            const unifiedEventTitles = (unifiedBody.data.events as any[])
                .filter((item: any) => [eventEarlierTitle, eventLaterTitle].includes(item.title))
                .map((item: any) => item.title);
            expect(unifiedEventTitles).toEqual([eventEarlierTitle, eventLaterTitle]);

            const unifiedTaskTitles = (unifiedBody.data.tasks as any[])
                .filter((item: any) => [taskEarlierTitle, taskLaterTitle].includes(item.title))
                .map((item: any) => item.title);
            expect(unifiedTaskTitles).toEqual([taskEarlierTitle, taskLaterTitle]);
        } finally {
            await userCtx.delete(`${baseURL}/api/v1/calendar/events/${eventEarlierBody.data.id}`).catch(() => {});
            await userCtx.delete(`${baseURL}/api/v1/calendar/events/${eventLaterBody.data.id}`).catch(() => {});
            await userCtx.delete(`${baseURL}/api/v1/calendar/tasks/${taskEarlierBody.data.id}`).catch(() => {});
            await userCtx.delete(`${baseURL}/api/v1/calendar/tasks/${taskLaterBody.data.id}`).catch(() => {});
        }
    });
});
