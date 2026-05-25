import { test, expect } from '@playwright/test';
import { getAdminContext, getUserContext, expectCustomResponse, logRequestPayload } from '../../utils/api-client.js';

/**
 * Assistant — Extended SSE & Error Coverage
 *
 * Supplements assistant.spec.ts with deeper validation:
 *   - Full SSE envelope ordering
 *   - tool_call event schema (tool_call_id, tool_name, progress, request/response)
 *   - Timing assertions (total stream, search response_time)
 *   - Error cases: 401, 400 (empty content), 404 (wrong thread)
 */

interface SseEvent {
    eventType: string;
    data: Record<string, unknown>;
}

function parseSse(raw: string): SseEvent[] {
    return raw.trim().split(/\n\n+/)
        .filter(b => b.trim())
        .map(block => {
            const lines = block.split('\n');
            const eventType = (lines.find(l => l.startsWith('event:')) ?? '').replace(/^event:\s*/, '').trim();
            const rawData  = (lines.find(l => l.startsWith('data:'))  ?? '').replace(/^data:\s*/,  '').trim();
            return { eventType, data: rawData ? JSON.parse(rawData) : {} };
        });
}

test.describe('Assistant — Extended SSE & Error Coverage', () => {
    let userContext: Awaited<ReturnType<typeof getUserContext>>;
    let adminContext: Awaited<ReturnType<typeof getAdminContext>>;
    let threadId: string;

    test.beforeAll(async ({ baseURL }) => {
        userContext = await getUserContext();
        adminContext = await getAdminContext();

        const response = await userContext.post(`${baseURL}/api/v1/assistant/threads`, {
            data: { name: 'Extended SSE Test Thread' }
        });
        const body = await response.json();
        threadId = body.data.id;
    });

    // ── JSON non-streaming ─────────────────────────────────────────────────
    test('Chat | stream=false returns JSON with message text', async ({ baseURL }) => {
        expect(threadId).toBeDefined();

        const payload = { content: 'Respond with exactly one word: hello', stream: false };

        const t0 = Date.now();
        const response = await userContext.post(
            `${baseURL}/api/v1/assistant/threads/${threadId}/chat`,
            { data: payload }
        );
        const elapsed = Date.now() - t0;

        const body = await expectCustomResponse(response, 200, true, payload, 'JSON Chat');
        expect(typeof body.data.message).toBe('string');
        expect(body.data.message.length).toBeGreaterThan(0);
        expect(response.headers()['content-type']).not.toContain('text/event-stream');

        // Verify title was updated away from "New Chat"
        const threadRes = await userContext.get(`${baseURL}/api/v1/assistant/threads/${threadId}`);
        const threadBody = await expectCustomResponse(threadRes, 200, true, null);
        expect(threadBody.data.name).not.toBe('New Chat');

        console.log(`\n⏱  JSON chat time: ${elapsed}ms`);
        console.log(`📝 Response: ${body.data.message.substring(0, 80)}`);
    });

    // ── SSE envelope order ─────────────────────────────────────────────────
    test('SSE | Event envelope ordering is correct', async ({ baseURL }) => {
        expect(threadId).toBeDefined();

        const payload = { content: 'Say one word.', stream: true };
        await logRequestPayload('POST', `${baseURL}/api/v1/assistant/threads/${threadId}/chat`, payload, 'SSE Envelope Order');

        const t0 = Date.now();
        const response = await userContext.post(
            `${baseURL}/api/v1/assistant/threads/${threadId}/chat`,
            { data: payload }
        );
        const elapsed = Date.now() - t0;

        expect(response.status()).toBe(200);
        expect(response.headers()['content-type']).toContain('text/event-stream');

        const events = parseSse(await response.text());
        await test.info().attach('🌊 SSE Envelope', { body: JSON.stringify(events, null, 2), contentType: 'application/json' });

        // Ordering
        expect(events.at(0)!.eventType).toBe('message_start');
        expect(events.at(-1)!.eventType).toBe('message_stop');
        expect(events.at(-2)!.eventType).toBe('message_delta');

        // message_start payload
        const msg = (events.at(0)!.data as any).message;
        expect(msg.role).toBe('assistant');
        expect(typeof msg.id).toBe('string');
        expect(typeof msg.model).toBe('string');

        // message_delta payload
        const md = events.at(-2)!.data as any;
        expect(md.delta.stop_reason).toBe('end_turn');
        expect(typeof md.usage.output_tokens).toBe('number');
        expect(md.usage.output_tokens).toBeGreaterThan(0);

        // At least one text delta
        const textDeltas = events.filter(e => e.eventType === 'content_block_delta');
        expect(textDeltas.length).toBeGreaterThan(0);
        for (const td of textDeltas) {
            expect((td.data as any).delta.type).toBe('text_delta');
            expect(typeof (td.data as any).delta.text).toBe('string');
        }

        console.log(`\n⏱  SSE stream time: ${elapsed}ms`);
        console.log(`📦 Events (${events.length}): ${events.map(e => e.eventType).join(' → ')}`);
    });

    // ── tool_call schema ───────────────────────────────────────────────────
    test('SSE | tool_call events have correct schema', async ({ baseURL }) => {
        expect(threadId).toBeDefined();

        const payload = { content: 'Search the web: latest news from India right now.', stream: true };
        await logRequestPayload('POST', `${baseURL}/api/v1/assistant/threads/${threadId}/chat`, payload, 'SSE Tool Call Schema');

        const t0 = Date.now();
        const response = await userContext.post(
            `${baseURL}/api/v1/assistant/threads/${threadId}/chat`,
            { data: payload }
        );
        const elapsed = Date.now() - t0;

        const events = parseSse(await response.text());
        await test.info().attach('🔧 SSE Tool Call Events', { body: JSON.stringify(events, null, 2), contentType: 'application/json' });

        const toolEvents = events.filter(e => e.eventType === 'tool_call');
        expect(toolEvents.length).toBeGreaterThanOrEqual(2);

        const startEvt = toolEvents.find(e => (e.data as any).status === 'start');
        const stopEvt  = toolEvents.find(e => (e.data as any).status === 'stop');
        expect(startEvt).toBeDefined();
        expect(stopEvt).toBeDefined();

        // ── start event ─────────────────────────────────────────────────
        const s = startEvt!.data as any;
        expect(s.type).toBe('tool_call');
        expect(s.status).toBe('start');
        expect(s.name).toBe('web_search');
        expect(s.id).toMatch(/^(tc_|tooluse_)/);
        expect(typeof s.progress).toBe('string');
        expect(s.progress.length).toBeGreaterThan(0);
        expect(typeof s.input?.query).toBe('string');
        expect(s.input.query.length).toBeGreaterThan(0);
        expect(typeof s.input?.timeout).toBe('number');
        expect(s.input.timeout).toBeGreaterThan(0);
        expect(typeof s.icon).toBe('string');

        // ── stop event ──────────────────────────────────────────────────
        const st = stopEvt!.data as any;
        expect(st.type).toBe('tool_call');
        expect(st.status).toBe('stop');
        expect(st.name).toBe('web_search');
        expect(st.id).toBe(s.id);  // IDs must match
        expect(typeof st.progress).toBe('string');
        expect(st.progress.length).toBeGreaterThan(0);
        expect(st.progress).not.toBe(s.progress);      // stop has different label from start
        expect(typeof st.input?.query).toBe('string');
        expect(typeof st.input?.timeout).toBe('number');
        expect(st.input.timeout).toBe(s.input.timeout);
        expect(typeof st.result).toBe('object');
        expect(Array.isArray(st.result?.data)).toBe(true);
        expect(st.result.data.length).toBeGreaterThan(0);
        for (const item of st.result.data) {
            expect(typeof item.url).toBe('string');
            expect(typeof item.title).toBe('string');
        }
        expect(typeof st.result?.response_time).toBe('number');
        expect(st.result.response_time).toBeGreaterThan(0);
        expect(st.result.response_time).toBeLessThan(30); // search must finish within 30s

        // start event must come before stop event in stream
        expect(events.indexOf(stopEvt!)).toBeGreaterThan(events.indexOf(startEvt!));

        // text content must follow the tool call
        const textDeltas = events.filter(e => e.eventType === 'content_block_delta');
        expect(textDeltas.length).toBeGreaterThan(0);

        console.log(`\n⏱  Web search SSE total time: ${elapsed}ms`);
        console.log(`🔍 id: ${s.id}`);
        console.log(`🔍 query: ${s.input.query}`);
        console.log(`📰 results: ${st.result.data.length}, search_time: ${st.result.response_time}s`);
        console.log(`📝 text deltas: ${textDeltas.length}`);
    });

    // ── Error cases ────────────────────────────────────────────────────────
    test('Error | 401 without auth token', async ({ baseURL }) => {
        const { request } = await import('@playwright/test');
        const anonCtx = await request.newContext({ baseURL: baseURL! });

        const response = await anonCtx.post(
            `${baseURL}/api/v1/assistant/threads/00000000-0000-0000-0000-000000000000/chat`,
            { data: { content: 'hello' } }
        );
        expect(response.status()).toBe(401);
    });

    test('Error | 400 when content is empty', async ({ baseURL }) => {
        expect(threadId).toBeDefined();

        const response = await userContext.post(
            `${baseURL}/api/v1/assistant/threads/${threadId}/chat`,
            { data: { content: '' } }
        );
        expect(response.status()).toBe(400);
    });

    test('Error | 400 when attachments is not a list', async ({ baseURL }) => {
        expect(threadId).toBeDefined();

        const response = await userContext.post(
            `${baseURL}/api/v1/assistant/threads/${threadId}/chat`,
            { data: { content: 'Hello', attachments: 'not-a-list' } }
        );
        expect(response.status()).toBe(400);

        const body = await response.json();
        expect(body.success).toBe(false);
        expect(body.error?.message).toBe('attachments must be a list');
    });

    test('Security | 404 when accessing another user thread', async ({ baseURL }) => {
        expect(threadId).toBeDefined();

        const response = await adminContext.post(
            `${baseURL}/api/v1/assistant/threads/${threadId}/chat`,
            { data: { content: 'Cross-user access attempt' } }
        );
        expect(response.status()).toBe(404);
    });

    test('Error | 404 for non-existent thread', async ({ baseURL }) => {
        const response = await userContext.get(
            `${baseURL}/api/v1/assistant/threads/00000000-0000-0000-0000-000000000000`
        );
        expect(response.status()).toBe(404);
    });

    // ── Cleanup ────────────────────────────────────────────────────────────
    test('Cleanup | Delete test thread', async ({ baseURL }) => {
        expect(threadId).toBeDefined();

        const response = await userContext.delete(
            `${baseURL}/api/v1/assistant/threads/${threadId}`
        );
        expect([200, 204]).toContain(response.status());

        const check = await userContext.get(`${baseURL}/api/v1/assistant/threads/${threadId}`);
        expect(check.status()).toBe(404);
    });
});
