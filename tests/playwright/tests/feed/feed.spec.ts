import { test, expect, type APIRequestContext } from '@playwright/test';
import { getUserContext, getAdminContext, expectCustomResponse, logRequestPayload, attachResponseToReport } from '../../utils/api-client';

async function uploadTempFile(ctx: APIRequestContext, baseURL: string, fileName = 'feed-attachment.jpg', contents = 'feed attachment') {
    const response = await ctx.post(`${baseURL}/api/v1/upload`, {
        multipart: {
            file: {
                name: fileName,
                mimeType: 'image/jpeg',
                buffer: Buffer.from(contents),
            },
        },
    });
    const body = await expectCustomResponse(response, 201, true, { file: `${fileName} (image/jpeg)` }, 'Feed attachment upload');
    return body.data.path;
}

test.describe('Feed API Rebuilt', () => {
    let userContext: APIRequestContext;
    let adminContext: APIRequestContext;
    let feedId: string;
    let commentId: string;
    let testCloseGroupId: string;

    test.beforeAll(async ({ baseURL }) => {
        userContext = await getUserContext();
        adminContext = await getAdminContext();

        // Retrieve the default close group ID to satisfy 'all' access type validation
        const listRes = await userContext.get(`${baseURL}/api/v1/close-group`);
        if (listRes.ok()) {
            const listBody = await listRes.json();
            if (listBody.success && Array.isArray(listBody.data) && listBody.data.length > 0) {
                testCloseGroupId = listBody.data[0].id;
            }
        }
    });

    test('Authenticated user can list feed', async ({ baseURL }) => {
        const response = await userContext.get(`${baseURL}/api/v1/feed?page=1&page_size=10`);
        const body = await expectCustomResponse(response, 200, true, null, 'List Feed');

        expect(Array.isArray(body.data)).toBe(true);
    });

    test('Unauthenticated request is rejected for feed', async ({ request, baseURL }) => {
        await logRequestPayload('GET', `${baseURL}/api/v1/feed`, null, 'List Feed - Unauthenticated');
        const response = await request.get(`${baseURL}/api/v1/feed`);
        expect([401, 403]).toContain(response.status());
        const body = await response.json().catch(() => ({}));
        await attachResponseToReport(body, 'List Feed - Unauthenticated');
    });

    test('User can create a generic text feed post with line breaks', async ({ baseURL }) => {
        const requestPayload = {
            body_text: `Line 1: Hello from Playwright!\nLine 2: Newline validation text.\nCreated at: ${Date.now()}`,
            media_urls: [],
            youtube_url: null,
            access_type: 'only_me',
            access_family_ids: [],
            access_close_group_ids: [],
            access_user_ids: []
        };

        const response = await userContext.post(`${baseURL}/api/v1/feed`, {
            data: requestPayload
        });

        const body = await expectCustomResponse(response, 201, true, requestPayload, 'Create Text Feed Post');
        expect(body.data).toHaveProperty('id');
        expect(typeof body.data.created_by).toBe('string');
        expect(body.data.creator_info).toHaveProperty('first_name');
        expect(body.data.creator_info.first_name).toBeDefined();
        if (body.data.creator_info.profile_image) {
            expect(body.data.creator_info.profile_image).toMatch(/^https?:\/\//);
        }
        feedId = body.data.id;
    });

    test('User can create a youtube feed post', async ({ baseURL }) => {
        const requestPayload = {
            body_text: 'Check this shared video!',
            media_urls: [],
            youtube_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            access_type: 'only_me',
            access_family_ids: [],
            access_close_group_ids: [],
            access_user_ids: []
        };

        const response = await userContext.post(`${baseURL}/api/v1/feed`, {
            data: requestPayload
        });

        const body = await expectCustomResponse(response, 201, true, requestPayload, 'Create Youtube Feed Post');
        expect(body.data).toHaveProperty('id');
    });

    test('Creating youtube post fails if media_urls is not empty', async ({ baseURL }) => {
        const requestPayload = {
            body_text: 'Failed post',
            media_urls: ['https://example.com/image.jpg'],
            youtube_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            access_type: 'only_me',
            access_family_ids: [],
            access_close_group_ids: [],
            access_user_ids: []
        };

        const response = await userContext.post(`${baseURL}/api/v1/feed`, {
            data: requestPayload
        });
        
        expect(response.status()).toBe(400);
        const body = await response.json();
        expect(body.success).toBe(false);
    });

    test('Creating a post fails if all content fields are empty', async ({ baseURL }) => {
        const requestPayload = {
            body_text: '',
            media_urls: [],
            youtube_url: null,
            external_urls: null,
            access_type: 'only_me',
            access_family_ids: [],
            access_close_group_ids: [],
            access_user_ids: []
        };

        const response = await userContext.post(`${baseURL}/api/v1/feed`, {
            data: requestPayload
        });
        
        expect(response.status()).toBe(400);
        const body = await response.json();
        expect(body.success).toBe(false);
    });

    test('User can create a feed post with external_urls only (no body_text)', async ({ baseURL }) => {
        const requestPayload = {
            body_text: null,
            media_urls: [],
            youtube_url: null,
            external_urls: ['https://example.com/article'],
            access_type: 'only_me',
            access_family_ids: [],
            access_close_group_ids: [],
            access_user_ids: [],
        };

        const response = await userContext.post(`${baseURL}/api/v1/feed`, {
            data: requestPayload,
        });

        const body = await expectCustomResponse(response, 201, true, requestPayload, 'Create Feed With External URLs');
        expect(body.data.external_urls).toEqual(['https://example.com/article']);
    });

    test('User can filter feed list by creator_id', async ({ baseURL }) => {
        expect(feedId).toBeDefined();

        const listRes = await userContext.get(`${baseURL}/api/v1/feed?page=1&page_size=50`);
        const listBody = await expectCustomResponse(listRes, 200, true, null, 'List Feed before creator filter');
        const createdFeed = listBody.data.find((f: { id: string }) => f.id === feedId);
        expect(createdFeed).toBeDefined();

        const creatorId = createdFeed.created_by;
        const filteredRes = await userContext.get(
            `${baseURL}/api/v1/feed?creator_id=${creatorId}&page=1&page_size=50`
        );
        const filteredBody = await expectCustomResponse(filteredRes, 200, true, null, 'List Feed by creator_id');
        expect(filteredBody.data.length).toBeGreaterThan(0);
        for (const item of filteredBody.data) {
            expect(item.created_by).toBe(creatorId);
        }
    });

    test('User can comment on a feed post', async ({ baseURL }) => {
        expect(feedId).toBeDefined();

        const requestPayload = {
            comment_text: 'Great post from Playwright!'
        };

        const response = await userContext.post(`${baseURL}/api/v1/feed/${feedId}/comments`, {
            data: requestPayload
        });

        const body = await expectCustomResponse(response, 200, true, requestPayload, 'Comment On Feed');
        expect(body.data).toHaveProperty('id');
        expect(body.data.comment_text).toBe('Great post from Playwright!');
        commentId = body.data.id;
    });

    test('User can get comments for a feed post', async ({ baseURL }) => {
        expect(feedId).toBeDefined();

        const response = await userContext.get(
            `${baseURL}/api/v1/feed/${feedId}/comments?page=1&page_size=10`
        );

        const body = await expectCustomResponse(response, 200, true, null, 'Get Feed Comments');
        expect(Array.isArray(body.data)).toBe(true);
        const found = body.data.find((c: any) => c.id === commentId);
        expect(found).toBeDefined();
        expect(found.user).toHaveProperty('id');
        expect(found.user).toHaveProperty('first_name');
    });

    test('User cannot comment twice on the same feed post', async ({ baseURL }) => {
        expect(feedId).toBeDefined();

        const requestPayload = {
            comment_text: 'Duplicate comment attempt'
        };

        const response = await userContext.post(`${baseURL}/api/v1/feed/${feedId}/comments`, {
            data: requestPayload
        });

        expect(response.status()).toBe(400);
        const body = await response.json();
        expect(body.success).toBe(false);
        expect(body.error.details.some((d: { message: string }) =>
            d.message.includes('You can only comment once per post')
        )).toBe(true);
    });

    test('User can update their own comment', async ({ baseURL }) => {
        expect(commentId).toBeDefined();

        const requestPayload = {
            comment_text: 'Updated comment text!'
        };

        const response = await userContext.patch(`${baseURL}/api/v1/feed/${feedId}/comments/${commentId}`, {
            data: requestPayload
        });

        const body = await expectCustomResponse(response, 200, true, requestPayload, 'Update Comment');
        expect(body.data.comment_text).toBe('Updated comment text!');
    });

    test('Another user cannot update someone else\'s comment', async ({ baseURL }) => {
        expect(commentId).toBeDefined();

        const requestPayload = {
            comment_text: 'Unauthorized update attempt'
        };

        const response = await adminContext.patch(`${baseURL}/api/v1/feed/${feedId}/comments/${commentId}`, {
            data: requestPayload
        });

        expect([400, 403]).toContain(response.status());
        const body = await response.json();
        expect(body.success).toBe(false);
    });

    test('Access control validation for all access type', async ({ baseURL }) => {
        // 1. Creating a post with 'all' access type and empty family/group IDs should fail
        const payloadEmpty = {
            body_text: 'Generic post',
            access_type: 'all',
            access_family_ids: [],
            access_close_group_ids: []
        };
        let response = await userContext.post(`${baseURL}/api/v1/feed`, { data: payloadEmpty });
        expect(response.status()).toBe(400);
        let body = await response.json();
        expect(body.success).toBe(false);
        expect(body.error.details.some((d: { message: string }) =>
            d.message.includes('At least one family ID or close group ID is required for all access')
        )).toBe(true);

        // 2. Creating a post with 'all' access type and non-empty access_user_ids should fail
        const payloadWithUsers = {
            body_text: 'Generic post',
            access_type: 'all',
            access_close_group_ids: [testCloseGroupId],
            access_user_ids: ['67ffd3f6-04fe-4fec-afbb-cd6b8ccb2eba']
        };
        response = await userContext.post(`${baseURL}/api/v1/feed`, { data: payloadWithUsers });
        expect(response.status()).toBe(400);
        body = await response.json();
        expect(body.success).toBe(false);
        expect(body.error.details.some((d: { message: string }) =>
            d.message.includes('access_user_ids must be empty for all access')
        )).toBe(true);
    });

    test('User can get a single feed post by id', async ({ baseURL }) => {
        expect(feedId).toBeDefined();

        const response = await userContext.get(`${baseURL}/api/v1/feed/${feedId}`);
        const body = await expectCustomResponse(response, 200, true, null, 'Get Feed Detail');
        expect(body.data.id).toBe(feedId);
        expect(body.data).toHaveProperty('creator_info');
    });

    test('Comment list returns pagination meta', async ({ baseURL }) => {
        expect(feedId).toBeDefined();

        const response = await userContext.get(
            `${baseURL}/api/v1/feed/${feedId}/comments?page=1&page_size=10`
        );
        const body = await expectCustomResponse(response, 200, true, null, 'Get Feed Comments Meta');
        expect(body.meta).toMatchObject({
            page: 1,
            page_size: 10,
            total: expect.any(Number),
            total_pages: expect.any(Number),
        });
    });

    test('User can react to a feed post', async ({ baseURL }) => {
        expect(feedId).toBeDefined();

        const requestPayload = {
            reaction: 'like'
        };

        const response = await userContext.post(`${baseURL}/api/v1/feed/${feedId}/react`, {
            data: requestPayload
        });

        const body = await expectCustomResponse(response, 200, true, requestPayload, 'React To Feed');
        expect(body.success).toBe(true);
        expect(body.data).toHaveProperty('id');
        expect(body.data.id).toBe(feedId);
        expect(body.data.reaction_count).toBe(1);
        expect(body.data.my_reaction).toBe('like');
        expect(body.data.reactions).toEqual({ like: 1 });

        // Verify reaction is in feed list
        const listResponse = await userContext.get(`${baseURL}/api/v1/feed?page=1&page_size=10`);
        const listBody = await expectCustomResponse(listResponse, 200, true, null, 'List Feed after Reaction');
        const updatedFeed = listBody.data.find((f: any) => f.id === feedId);
        expect(updatedFeed).toBeDefined();
        expect(updatedFeed.reaction_count).toBe(1);
        expect(updatedFeed.my_reaction).toBe('like');
        expect(updatedFeed.reactions).toEqual({ like: 1 });
    });

    test('User can remove a reaction (toggle) by sending null', async ({ baseURL }) => {
        expect(feedId).toBeDefined();

        const requestPayload = {
            reaction: null
        };

        const response = await userContext.post(`${baseURL}/api/v1/feed/${feedId}/react`, {
            data: requestPayload
        });

        const body = await expectCustomResponse(response, 200, true, requestPayload, 'Remove Reaction');
        expect(body.success).toBe(true);
        expect(body.data).toHaveProperty('id');
        expect(body.data.id).toBe(feedId);
        expect(body.data.reaction_count).toBe(0);
        expect(body.data.my_reaction).toBeNull();
        expect(body.data.reactions).toEqual({});

        // Verify reaction is removed in feed list
        const listResponse = await userContext.get(`${baseURL}/api/v1/feed?page=1&page_size=10`);
        const listBody = await expectCustomResponse(listResponse, 200, true, null, 'List Feed after Removing Reaction');
        const updatedFeed = listBody.data.find((f: any) => f.id === feedId);
        expect(updatedFeed).toBeDefined();
        expect(updatedFeed.reaction_count).toBe(0);
        expect(updatedFeed.my_reaction).toBeNull();
        expect(updatedFeed.reactions).toEqual({});
    });

    test('Reacting fails with invalid emoji name', async ({ baseURL }) => {
        expect(feedId).toBeDefined();

        const requestPayload = {
            reaction: 'INVALID_EMOJI'
        };

        const response = await userContext.post(`${baseURL}/api/v1/feed/${feedId}/react`, {
            data: requestPayload
        });
        
        expect(response.status()).toBe(400);
    });

    test('User can save a feed post', async ({ baseURL }) => {
        expect(feedId).toBeDefined();

        const response = await userContext.post(`${baseURL}/api/v1/feed/${feedId}/save`);
        const body = await expectCustomResponse(response, 200, true, null, 'Save Feed');
        expect(body.success).toBe(true);
        expect(body.data.id).toBe(feedId);
        expect(body.data.is_saved).toBe(true);

        const listResponse = await userContext.get(`${baseURL}/api/v1/feed?page=1&page_size=10`);
        const listBody = await expectCustomResponse(listResponse, 200, true, null, 'List Feed after Save');
        const updatedFeed = listBody.data.find((f: { id: string }) => f.id === feedId);
        expect(updatedFeed).toBeDefined();
        expect(updatedFeed.is_saved).toBe(true);

        const detailResponse = await userContext.get(`${baseURL}/api/v1/feed/${feedId}`);
        const detailBody = await expectCustomResponse(detailResponse, 200, true, null, 'Get Feed after Save');
        expect(detailBody.data.is_saved).toBe(true);
    });

    test('User can list saved feed posts', async ({ baseURL }) => {
        expect(feedId).toBeDefined();

        const response = await userContext.get(`${baseURL}/api/v1/feed/saved?page=1&page_size=10`);
        const body = await expectCustomResponse(response, 200, true, null, 'List Saved Feeds');
        expect(Array.isArray(body.data)).toBe(true);
        expect(body.meta).toMatchObject({
            page: 1,
            page_size: 10,
            total: expect.any(Number),
            total_pages: expect.any(Number),
        });

        const savedFeed = body.data.find((f: { id: string }) => f.id === feedId);
        expect(savedFeed).toBeDefined();
        expect(savedFeed.is_saved).toBe(true);
    });

    test('User can unsave a feed post', async ({ baseURL }) => {
        expect(feedId).toBeDefined();

        const response = await userContext.delete(`${baseURL}/api/v1/feed/${feedId}/save`);
        const body = await expectCustomResponse(response, 200, true, null, 'Unsave Feed');
        expect(body.success).toBe(true);
        expect(body.data.id).toBe(feedId);
        expect(body.data.is_saved).toBe(false);

        const listResponse = await userContext.get(`${baseURL}/api/v1/feed?page=1&page_size=10`);
        const listBody = await expectCustomResponse(listResponse, 200, true, null, 'List Feed after Unsave');
        const updatedFeed = listBody.data.find((f: { id: string }) => f.id === feedId);
        expect(updatedFeed).toBeDefined();
        expect(updatedFeed.is_saved).toBe(false);

        const savedListResponse = await userContext.get(`${baseURL}/api/v1/feed/saved?page=1&page_size=10`);
        const savedListBody = await expectCustomResponse(savedListResponse, 200, true, null, 'List Saved Feeds after Unsave');
        const savedFeed = savedListBody.data.find((f: { id: string }) => f.id === feedId);
        expect(savedFeed).toBeUndefined();
    });

    test('User can share a feed post', async ({ baseURL }) => {
        expect(feedId).toBeDefined();

        const requestPayload = {
            platform: 'whatsapp'
        };

        const response = await userContext.post(`${baseURL}/api/v1/feed/${feedId}/share`, {
            data: requestPayload
        });

        const body = await expectCustomResponse(response, 200, true, requestPayload, 'Share Feed');
        expect(body.success).toBe(true);
    });

    test('User can delete their own comment', async ({ baseURL }) => {
        expect(commentId).toBeDefined();

        const response = await userContext.delete(`${baseURL}/api/v1/feed/${feedId}/comments/${commentId}`);

        const body = await expectCustomResponse(response, 200, true, null, 'Delete Feed Comment');
        expect(body.success).toBe(true);
    });

    test('User can create feed with temp media and files are moved', async ({ baseURL }) => {
        const tempPath = await uploadTempFile(userContext, baseURL!);
        const payload = {
            body_text: 'Feed with attachments',
            media_urls: [tempPath],
            access_type: 'only_me',
        };

        const response = await userContext.post(`${baseURL}/api/v1/feed`, {
            data: payload,
        });

        const body = await expectCustomResponse(response, 201, true, payload, 'Create Feed with Attachments');
        expect(body.data).toHaveProperty('id');
        expect(body.data.media_urls).toHaveLength(1);
        expect(body.data.media_urls[0]).toContain('feeds/');
    });

    test('Reject feed creation with non-existent temp media', async ({ baseURL }) => {
        const payload = {
            body_text: 'Missing media post',
            media_urls: ['temp/00000000-0000-0000-0000-000000000000/nonexistent.jpg'],
            access_type: 'only_me',
        };

        const response = await userContext.post(`${baseURL}/api/v1/feed`, {
            data: payload,
        });

        expect(response.status()).toBe(400);
        const body = await response.json();
        expect(body.success).toBe(false);
    });

    test('Reject feed creation with unauthorized media path (another user or invalid path)', async ({ baseURL }) => {
        const payload = {
            body_text: 'Unauthorized media post',
            media_urls: ['temp/another-user-uuid/file.jpg'],
            access_type: 'only_me',
        };

        const response = await userContext.post(`${baseURL}/api/v1/feed`, {
            data: payload,
        });

        expect(response.status()).toBe(400);
    });

    test('Reject feed creation with directory traversal path', async ({ baseURL }) => {
        const payload = {
            body_text: 'Traversal media post',
            media_urls: ['temp/../etc/passwd'],
            access_type: 'only_me',
        };

        const response = await userContext.post(`${baseURL}/api/v1/feed`, {
            data: payload,
        });

        expect(response.status()).toBe(400);
    });

    test('User can update feed post text, access control, and media files', async ({ baseURL }) => {
        expect(feedId).toBeDefined();

        // 1. Upload two new temp files
        const tempPath1 = await uploadTempFile(userContext, baseURL!, 'temp1.jpg', 'temp 1 contents');
        const tempPath2 = await uploadTempFile(userContext, baseURL!, 'temp2.jpg', 'temp 2 contents');

        // 2. Update feed to have these two media urls
        let updatePayload: any = {
            body_text: 'Updated text body!',
            media_urls: [tempPath1, tempPath2],
            access_type: 'all',
            access_close_group_ids: [testCloseGroupId],
        };

        let response = await userContext.patch(`${baseURL}/api/v1/feed/${feedId}`, {
            data: updatePayload,
        });

        let body = await expectCustomResponse(response, 200, true, updatePayload, 'Update Feed Media');
        expect(body.data.body_text).toBe('Updated text body!');
        expect(body.data.access_type).toBe('all');
        expect(body.data.media_urls).toHaveLength(2);
        expect(body.data.media_urls[0]).toContain('feeds/');
        expect(body.data.media_urls[1]).toContain('feeds/');

        const savedMedia1 = body.data.media_urls[0];
        const savedMedia2 = body.data.media_urls[1];

        // 3. Upload a third temp file and update post to keep media1, remove media2, and add media3
        const tempPath3 = await uploadTempFile(userContext, baseURL!, 'temp3.jpg', 'temp 3 contents');
        updatePayload = {
            media_urls: [savedMedia1, tempPath3],
        };

        response = await userContext.patch(`${baseURL}/api/v1/feed/${feedId}`, {
            data: updatePayload,
        });

        body = await expectCustomResponse(response, 200, true, updatePayload, 'Update Feed Keep/Remove/Add Media');
        expect(body.data.media_urls).toHaveLength(2);
        expect(body.data.media_urls).toContain(savedMedia1);
        expect(body.data.media_urls.find((url: string) => url.includes('temp3'))).toBeDefined();
        expect(body.data.media_urls).not.toContain(savedMedia2);
    });

    test('User can fully update feed post via PUT', async ({ baseURL }) => {
        expect(feedId).toBeDefined();

        const updatePayload = {
            body_text: 'Full replace via PUT',
            media_urls: [],
            youtube_url: null,
            external_urls: null,
            access_type: 'only_me',
            access_family_ids: [],
            access_close_group_ids: [],
            access_user_ids: [],
        };

        const response = await userContext.put(`${baseURL}/api/v1/feed/${feedId}`, {
            data: updatePayload,
        });

        const body = await expectCustomResponse(response, 200, true, updatePayload, 'Update Feed via PUT');
        expect(body.data.body_text).toBe('Full replace via PUT');
    });

    test('User can delete their own feed post', async ({ baseURL }) => {
        expect(feedId).toBeDefined();

        const response = await userContext.delete(`${baseURL}/api/v1/feed/${feedId}`);

        const body = await expectCustomResponse(response, 200, true, null, 'Delete Feed Post');
        expect(body.success).toBe(true);
    });
});
