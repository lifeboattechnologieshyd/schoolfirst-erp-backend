import { test, expect } from '@playwright/test';
import { getUserContext, expectCustomResponse, logRequestPayload } from '../../utils/api-client';

test.describe('Docusafe Assistant Chat Integration', () => {
    let userContext: Awaited<ReturnType<typeof getUserContext>>;
    let threadId: string;

    let fileId: string;
    let folderId: string;

    test.beforeAll(async ({ baseURL }) => {
        userContext = await getUserContext();

        // 1. Create a folder first
        const folderRes = await userContext.post(`${baseURL}/api/v1/docusafe/folders`, {
            data: { name: `Chat Test Folder ${Date.now()}` }
        });
        const folderBody = await folderRes.json();
        if (!folderBody.success) {
            console.error('Folder creation failed:', JSON.stringify(folderBody, null, 2));
            throw new Error('Folder creation failed');
        }
        folderId = folderBody.data.id;

        // 2. Upload a test file to the folder
        const fileContent = Buffer.from('test content');
        const response = await userContext.post(`${baseURL}/api/v1/docusafe/folders/${folderId}/files`, {
            multipart: {
                file: {
                    name: 'test.txt',
                    mimeType: 'text/plain',
                    buffer: fileContent,
                },
                file_name: 'test.txt'
            }
        });
        const body = await response.json();
        if (!body.success) {
            console.error('File upload failed:', JSON.stringify(body, null, 2));
            throw new Error('File upload failed');
        }
        fileId = body.data.id;
    });

    test('User can create Docusafe thread with empty file ids', async ({ baseURL }) => {
        const requestPayload = {
            name: 'Docusafe Chat',
            module_settings: {
                module_name: 'docusafe',
                docusafe_file_ids: []
            }
        };

        const response = await userContext.post(`${baseURL}/api/v1/assistant/threads`, {
            data: requestPayload
        });

        const body = await expectCustomResponse(response, 200, true, requestPayload, 'Create Docusafe Thread');
        expect(body.data).toHaveProperty('id');
        expect(body.data.module_settings.module_name).toBe('docusafe');
        expect(body.data.module_settings.docusafe_file_ids).toEqual([]);
        threadId = body.data.id;
    });

    test('Chat with empty file ids triggers prompt to attach files', async ({ baseURL }) => {
        expect(threadId).toBeDefined();

        const requestPayload = {
            content: 'Summarize my documents',
            stream: false,
        };

        const response = await userContext.post(`${baseURL}/api/v1/assistant/threads/${threadId}/chat`, {
            data: requestPayload
        });

        const body = await expectCustomResponse(response, 200, true, requestPayload, 'Empty Files Prompt Check');
        
        // Assistant should respond with a message indicating files need to be attached
        expect(body.data).toHaveProperty('message');
        const text = body.data.message.toLowerCase();
        expect(text).toMatch(/attach|provide/);
        
        // Assert intent_name bypass
        expect(body.data.intent_name).toBe('docusafe_qa');
    });

    test('User can update Docusafe thread to include file ids', async ({ baseURL }) => {
        expect(threadId).toBeDefined();

        const requestPayload = {
            module_settings: {
                module_name: 'docusafe',
                docusafe_file_ids: [fileId]
            }
        };

        const response = await userContext.patch(`${baseURL}/api/v1/assistant/threads/${threadId}`, {
            data: requestPayload
        });

        const body = await expectCustomResponse(response, 200, true, requestPayload);
        expect(body.data.module_settings.module_name).toBe('docusafe');
        expect(body.data.module_settings.docusafe_file_ids).toEqual([fileId]);
    });

    test('Chat with file ids triggers search_docusafe tool', async ({ baseURL }) => {
        expect(threadId).toBeDefined();

        const requestPayload = {
            content: 'What is inside my document?',
            stream: true,
        };

        await logRequestPayload('POST', `${baseURL}/api/v1/assistant/threads/${threadId}/chat`, requestPayload, 'Chat Streaming — Docusafe');

        const response = await userContext.post(`${baseURL}/api/v1/assistant/threads/${threadId}/chat`, {
            data: requestPayload
        });

        expect(response.status()).toBe(200);
        expect(response.headers()['content-type']).toContain('text/event-stream');

        const body = await response.text();

        interface SseEvent { eventType: string; data: Record<string, unknown>; }
        const events: SseEvent[] = body.trim().split(/\n\n+/)
            .filter(b => b.trim())
            .map(block => {
                const lines = block.split('\n');
                const eventType = (lines.find(l => l.startsWith('event:')) ?? '').replace(/^event:\s*/, '').trim();
                const rawData  = (lines.find(l => l.startsWith('data:'))  ?? '').replace(/^data:\s*/,  '').trim();
                return { eventType, data: rawData ? JSON.parse(rawData) : {} };
            });

        // intent_selected event should be docusafe_qa
        const intentEvent = events.find(e => e.eventType === 'intent_selected');
        expect(intentEvent).toBeDefined();
        expect((intentEvent!.data as any).intent_name).toBe('docusafe_qa');

        const toolCallEvents = events.filter(e => e.eventType === 'tool_call');
        expect(toolCallEvents.length).toBeGreaterThan(0);

        const toolStart = toolCallEvents.find(e => (e.data as any).status === 'start');
        expect(toolStart).toBeDefined();
        const startD = toolStart!.data as any;
        expect(startD.name).toBe('search_docusafe');
    });

    test('Cleanup: delete docusafe thread', async ({ baseURL }) => {
        expect(threadId).toBeDefined();
        const response = await userContext.delete(`${baseURL}/api/v1/assistant/threads/${threadId}`);
        expect([200, 204]).toContain(response.status());
    });
});
