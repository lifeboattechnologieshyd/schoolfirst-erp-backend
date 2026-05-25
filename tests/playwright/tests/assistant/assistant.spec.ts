import { test, expect } from '@playwright/test';
import { getUserContext, expectCustomResponse, logRequestPayload } from '../../utils/api-client';

test.describe('Assistant API CRUD', () => {
    let userContext: Awaited<ReturnType<typeof getUserContext>>;
    let threadId: string;

    test.beforeAll(async ({ baseURL }) => {
        userContext = await getUserContext();

        const response = await userContext.post(`${baseURL}/api/v1/assistant/threads`, {
            data: { name: 'Test Thread' }
        });
        const body = await response.json();
        threadId = body.data.id;
    });

    test('User can list threads', async ({ baseURL }) => {
        const response = await userContext.get(`${baseURL}/api/v1/assistant/threads`);
        const body = await expectCustomResponse(response, 200, true, null);

        expect(Array.isArray(body.data?.results || body.data)).toBeTruthy();
    });

    test('User can get specific thread', async ({ baseURL }) => {
        expect(threadId).toBeDefined();

        const response = await userContext.get(`${baseURL}/api/v1/assistant/threads/${threadId}`);
        const body = await expectCustomResponse(response, 200, true, null, 'Get Thread Details');

        expect(body.data.id).toBe(threadId);
    });

    test('User can send message to thread (JSON response with stream=false)', async ({ baseURL }) => {
        expect(threadId).toBeDefined();

        const requestPayload = {
            content: 'Hello Assistant! Give me a brief response.',
            stream: false,  // Explicitly disable streaming
        };

        const t0 = Date.now();
        const response = await userContext.post(`${baseURL}/api/v1/assistant/threads/${threadId}/chat`, {
            data: requestPayload
        });
        const elapsed = Date.now() - t0;

        // Verify standard JSON CustomResponse format
        const body = await expectCustomResponse(response, 200, true, requestPayload, 'Chat JSON Response');

        // Response should have direct message text
        expect(body.data).toHaveProperty('message');
        expect(typeof body.data.message).toBe('string');
        expect(body.data.message.length).toBeGreaterThan(0);

        // Should NOT be a streaming response
        const contentType = response.headers()['content-type'] || '';
        expect(contentType).not.toContain('text/event-stream');

        // Verify title was updated away from "New Chat"
        const threadRes = await userContext.get(`${baseURL}/api/v1/assistant/threads/${threadId}`);
        const threadBody = await expectCustomResponse(threadRes, 200, true, null);
        expect(threadBody.data.name).not.toBe('New Chat');

        console.log(`\n⏱  JSON chat response time: ${elapsed}ms`);
        console.log(`📝 Response preview: ${body.data.message.substring(0, 80)}`);
    });

    test('User can send message to thread (SSE streaming with stream=true)', async ({ baseURL }) => {
        expect(threadId).toBeDefined();

        const requestPayload = {
            content: 'Tell me a fun fact in one sentence.',
            stream: true,  // Explicitly enable streaming
        };

        // Log request payload for streaming requests
        await logRequestPayload('POST', `${baseURL}/api/v1/assistant/threads/${threadId}/chat`, requestPayload, 'Chat Streaming');

        const t0 = Date.now();
        const response = await userContext.post(`${baseURL}/api/v1/assistant/threads/${threadId}/chat`, {
            data: requestPayload
        });
        const elapsed = Date.now() - t0;

        // Verify SSE response format
        expect(response.status()).toBe(200);
        const contentType = response.headers()['content-type'] || '';
        expect(contentType).toContain('text/event-stream');

        const body = await response.text();

        // Attach streaming response for visibility
        await test.info().attach('🌊 Streaming Response (Chat)', {
            body: body,
            contentType: 'text/plain'
        });

        // ── Parse SSE events ───────────────────────────────────────────────
        interface SseEvent {
            eventType: string;
            data: Record<string, unknown>;
        }

        const parseSse = (raw: string): SseEvent[] =>
            raw.trim().split(/\n\n+/)
               .filter(b => b.trim() !== '')
               .map(block => {
                   const lines = block.split('\n');
                   const eventType = (lines.find(l => l.startsWith('event:')) ?? '').replace(/^event:\s*/, '').trim();
                   const rawData  = (lines.find(l => l.startsWith('data:'))  ?? '').replace(/^data:\s*/,  '').trim();
                   return { eventType, data: rawData ? JSON.parse(rawData) : {} };
               });

        const events = parseSse(body);
        expect(events.length).toBeGreaterThan(2);

        // 1. First event must be message_start with assistant role
        const firstEvent = events.at(0)!;
        expect(firstEvent.eventType).toBe('message_start');
        expect((firstEvent.data as any).message?.role).toBe('assistant');
        expect(typeof (firstEvent.data as any).message?.id).toBe('string');

        // 2. Last event must be message_stop
        expect(events.at(-1)!.eventType).toBe('message_stop');

        // 3. Second-to-last must be message_delta with stop_reason and usage
        const deltaMsg = events.at(-2)!;
        expect(deltaMsg.eventType).toBe('message_delta');
        expect((deltaMsg.data as any).delta?.stop_reason).toBe('end_turn');
        expect(typeof (deltaMsg.data as any).usage?.output_tokens).toBe('number');

        // 4. At least one content_block_start + content_block_stop pair
        expect(events.some(e => e.eventType === 'content_block_start')).toBe(true);
        expect(events.some(e => e.eventType === 'content_block_stop')).toBe(true);

        // 5. content_block_delta events have text_delta structure
        const deltaEvents = events.filter(e => e.eventType === 'content_block_delta');
        expect(deltaEvents.length).toBeGreaterThan(0);
        for (const evt of deltaEvents) {
            expect((evt.data as any).delta?.type).toBe('text_delta');
            expect(typeof (evt.data as any).delta?.text).toBe('string');
        }

        // 6. Accumulated text is non-empty
        const accumulatedText = deltaEvents
            .map(e => (e.data as any).delta?.text ?? '')
            .join('');
        expect(accumulatedText.length).toBeGreaterThan(0);

        console.log(`\n⏱  SSE stream total time: ${elapsed}ms`);
        console.log(`📦 Event types: ${events.map(e => e.eventType).join(' → ')}`);
        console.log(`📝 Accumulated text (first 120): ${accumulatedText.substring(0, 120)}`);
    });

    test('SSE streaming — tool_call events (web search)', async ({ baseURL }) => {
        expect(threadId).toBeDefined();

        const requestPayload = {
            content: 'What is the latest news about India today?',
            stream: true,
        };

        await logRequestPayload('POST', `${baseURL}/api/v1/assistant/threads/${threadId}/chat`, requestPayload, 'Chat Streaming — Web Search');

        const t0 = Date.now();
        const response = await userContext.post(`${baseURL}/api/v1/assistant/threads/${threadId}/chat`, {
            data: requestPayload
        });
        const elapsed = Date.now() - t0;

        expect(response.status()).toBe(200);
        expect(response.headers()['content-type']).toContain('text/event-stream');

        const body = await response.text();
        await test.info().attach('🌊 SSE Stream — Web Search', { body, contentType: 'text/plain' });

        interface SseEvent { eventType: string; data: Record<string, unknown>; }
        const events: SseEvent[] = body.trim().split(/\n\n+/)
            .filter(b => b.trim())
            .map(block => {
                const lines = block.split('\n');
                const eventType = (lines.find(l => l.startsWith('event:')) ?? '').replace(/^event:\s*/, '').trim();
                const rawData  = (lines.find(l => l.startsWith('data:'))  ?? '').replace(/^data:\s*/,  '').trim();
                return { eventType, data: rawData ? JSON.parse(rawData) : {} };
            });

        // ── Envelope checks ──────────────────────────────────────────────
        expect(events.at(0)!.eventType).toBe('message_start');
        expect(events.at(-1)!.eventType).toBe('message_stop');
        expect(events.at(-2)!.eventType).toBe('message_delta');

        // ── tool_call events ─────────────────────────────────────────────
        const toolCallEvents = events.filter(e => e.eventType === 'tool_call');
        expect(toolCallEvents.length).toBeGreaterThanOrEqual(2); // at least start + stop

        const toolStart = toolCallEvents.find(e => (e.data as any).status === 'start');
        const toolStop  = toolCallEvents.find(e => (e.data as any).status === 'stop');

        expect(toolStart).toBeDefined();
        expect(toolStop).toBeDefined();

        // start event shape
        const startD = toolStart!.data as any;
        expect(startD.type).toBe('tool_call');
        expect(startD.name).toBe('web_search');
        expect(typeof startD.id).toBe('string');
        expect(startD.id).toMatch(/^(tc_|tooluse_)/);
        expect(typeof startD.progress).toBe('string');
        expect(startD.progress.length).toBeGreaterThan(0);
        expect(typeof startD.input?.query).toBe('string');
        expect(typeof startD.icon).toBe('string');

        // stop event shape
        const stopD = toolStop!.data as any;
        expect(stopD.type).toBe('tool_call');
        expect(stopD.name).toBe('web_search');
        expect(stopD.id).toBe(startD.id); // same ID
        expect(typeof stopD.progress).toBe('string');
        expect(stopD.progress.length).toBeGreaterThan(0);
        expect(typeof stopD.input?.query).toBe('string');
        expect(typeof stopD.result).toBe('object');
        expect(typeof stopD.result?.response_time).toBe('number');
        expect(Array.isArray(stopD.result?.data)).toBe(true);
        expect(stopD.result.data.length).toBeGreaterThan(0);
        expect(typeof stopD.result.data[0].url).toBe('string');
        expect(typeof stopD.result.data[0].title).toBe('string');

        // ── Content must follow the tool call ────────────────────────────
        const deltaEvents = events.filter(e => e.eventType === 'content_block_delta');
        expect(deltaEvents.length).toBeGreaterThan(0);
        const accumulatedText = deltaEvents.map(e => (e.data as any).delta?.text ?? '').join('');
        expect(accumulatedText.length).toBeGreaterThan(0);

        // ── Timing ───────────────────────────────────────────────────────
        const toolStartIdx = events.indexOf(toolStart!);
        const toolStopIdx  = events.indexOf(toolStop!);
        expect(toolStopIdx).toBeGreaterThan(toolStartIdx);

        console.log(`\n⏱  Web search SSE total time: ${elapsed}ms`);
        console.log(`📦 Event types: ${events.map(e => e.eventType).join(' → ')}`);
        console.log(`🔍 Tool call ID: ${startD.id}`);
        console.log(`🔍 Search query: ${startD.input?.query}`);
        console.log(`📰 Result count: ${stopD.result?.data?.length}`);
        console.log(`📝 Response preview (120): ${accumulatedText.substring(0, 120)}`);
    });

    test('User can send message with default stream behavior', async ({ baseURL }) => {
        expect(threadId).toBeDefined();

        const requestPayload = {
            content: 'What is 2+2?',
            // Omitting 'stream' flag entirely - behavior defaults to true
        };

        const response = await userContext.post(`${baseURL}/api/v1/assistant/threads/${threadId}/chat`, {
            data: requestPayload
        });

        expect(response.status()).toBe(200);

        const contentType = response.headers()['content-type'] || '';

        // Check which format we got and verify accordingly
        if (contentType.includes('text/event-stream')) {
            // Log request for streaming
            await logRequestPayload('POST', `${baseURL}/api/v1/assistant/threads/${threadId}/chat`, requestPayload, 'Chat Default (Streaming)');
            // Got streaming response
            const body = await response.text();
            expect(body).toContain('data:');
            console.log('✅ Default behavior: Streaming enabled');
        } else {
            // Got JSON response
            const body = await expectCustomResponse(response, 200, true, requestPayload, 'Chat Default');
            expect(body.data).toHaveProperty('message');
            expect(typeof body.data.message).toBe('string');
            console.log('✅ Default behavior: JSON response');
        }
    });

    test('User can list messages for thread', async ({ baseURL }) => {
        expect(threadId).toBeDefined();

        const response = await userContext.get(`${baseURL}/api/v1/assistant/threads/${threadId}/messages`);
        const body = await expectCustomResponse(response, 200, true, null, 'List Messages');

        expect(Array.isArray(body.data?.results || body.data)).toBeTruthy();
    });

    test('User can update thread', async ({ baseURL }) => {
        expect(threadId).toBeDefined();

        const requestPayload = {
            name: 'Updated Thread Title',
        };

        const response = await userContext.patch(`${baseURL}/api/v1/assistant/threads/${threadId}`, {
            data: requestPayload
        });

        const body = await expectCustomResponse(response, 200, true, requestPayload);
        expect(body.data.name).toBe('Updated Thread Title');
    });

    test('User can delete thread', async ({ baseURL }) => {
        expect(threadId).toBeDefined();

        const response = await userContext.delete(`${baseURL}/api/v1/assistant/threads/${threadId}`);

        expect([200, 204]).toContain(response.status());
        // Ensure it's actually deleted
        const getRes = await userContext.get(`${baseURL}/api/v1/assistant/threads/${threadId}`);
        expect(getRes.status()).toBe(404);
    });

});
