# Docusafe Module — Implementation Plan

## 1. Overview

Docusafe is a family-scoped online document vault. Users create **root-level folders** (no nesting/sub-directories), upload **files** into those folders, and share them in two ways:

1. **File Sharing** — Grant **read-only** file-level access to an entire family or to specific users (must be members of the owner's family).
2. **Temporary File Shares** — Generate password-protected, time-limited, trackable links for one or more files. Can be shared with anyone.

### Key Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **No ForeignKeys** — all cross-model references use `UUIDField` | Loose coupling |
| 2 | **File-level access only** — no folder-level grants | Explicit control; frontend derives folder view from shared files |
| 3 | **All sharing is read-only** — no MANAGE/WRITE access for shared users | Only the folder owner can manage files |
| 4 | **File type whitelist** — only `ALLOWED_EXTENSIONS` permitted | Security |
| 5 | **Expired share cleanup via cron** — 7-day retention then hard-delete | Keep DB lean |
| 6 | **Store file paths only** — pre-signed URLs generated on-the-fly | No stale URLs |
| 7 | **Per-file and per-folder size limits + max files per folder** | Prevent abuse |
| 8 | **Backend-managed uploads only** | Simpler, auth enforced server-side |
| 9 | **Multi-file temporary shares** — one link can contain files from across folders | Flexible sharing |
| 10 | **No file versioning / no soft-delete recovery** | Simpler model |
| 11 | **Brute-force protection** — auto-block after threshold, success resets counter | Security |
| 12 | **Folder scoped to one family** | Clear ownership |
| 13 | **No custom permission classes** — `IsAuthenticated` only, access logic in services | Simpler, modular |
| 14 | **No separate share_token** — use share UUID (`id`) directly in URLs | Simpler, less confusion |
| 15 | **Service-layer architecture** — views are thin, all logic in services | Modular, testable |

---

## 2. Architecture Approach

### Service-Layer Pattern

All business logic lives in the **service layer** (`apps/docusafe/services/`). Views/API endpoints are **thin wrappers** that:
1. Deserialize the request (via serializers).
2. Call the appropriate service method.
3. Return the response.

Views **must not** contain business logic, database queries, access checks, or S3 operations. This ensures:
- **Testability** — services can be unit-tested independently of HTTP.
- **Reusability** — the same service method can be called from views, management commands, or cron jobs.
- **Separation of concerns** — serializers handle validation, services handle logic, views handle HTTP.

```
Request → View (deserialize) → Service (logic + DB + S3) → View (serialize response)
```

### Permissions

**No custom Django permission classes.** All endpoints use `permission_classes = [IsAuthenticated]` except the public share access endpoint (`AllowAny`).

Access control is enforced **inside service methods** — every service method validates that the requesting user has the right to perform the action (ownership check, family membership check, etc.).

---

## 3. Data Model Design

> All cross-model references use `UUIDField` — **no ForeignKeys**. Cascade deletes are handled manually in the service layer.

### 3.1. Enums (in `shared/enums/base.py`)

```python
class DocusafeAccessType(models.TextChoices):
    FAMILY = "FAMILY", "Family"   # Entire family gets read-only access
    USER = "USER", "User"         # Specific user gets read-only access

class TemporaryShareStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    DISABLED = "DISABLED", "Disabled"
    EXPIRED = "EXPIRED", "Expired"
    BLOCKED = "BLOCKED", "Blocked"
```

### 3.2. Folder (`apps/docusafe/models/folder.py`)

```
Table: docusafe_folder
```

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUIDField (PK) | `default=uuid.uuid4` |
| `name` | CharField(255) | Folder display name |
| `description` | TextField (nullable) | Optional description |
| `remarks` | TextField (nullable) | Optional remarks / notes |
| `family_id` | UUIDField | References `Family.id` — scoped to one family |
| `owner_id` | UUIDField | References `UserMaster.id` — the individual who owns this folder |
| `file_count` | PositiveIntegerField | Default 0 — **denormalized** |
| `total_size` | BigIntegerField | Default 0 bytes — **denormalized** |
| `is_shared` | BooleanField | Default `False` — `True` when any file in this folder is in an active temporary share |
| *AuditModel fields* | — | |

**Indexes:** `family_id`, `owner_id`, `created_by`, `is_shared`
**Unique constraint:** `(family_id, owner_id, name)`

> **File size, folder size, and max file count limits** are enforced as **global platform constants** (see `constants.py` in Section 11), not stored per-folder.

### 3.3. File (`apps/docusafe/models/file.py`)

```
Table: docusafe_file
```

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUIDField (PK) | |
| `folder_id` | UUIDField | References `DocusafeFolder.id` |
| `file_name` | CharField(500) | Original file name |
| `description` | TextField (nullable) | Optional description |
| `remarks` | TextField (nullable) | Optional remarks / notes |
| `file_path` | CharField(1024) | S3 object key (see Section 4) |
| `mime_type` | CharField(255) | e.g. `application/pdf` |
| `file_size` | BigIntegerField | Size in bytes |
| `file_extension` | CharField(50) | e.g. `.pdf`, `.jpg` |
| `checksum` | CharField(128, nullable) | SHA-256 hash |
| `family_id` | UUIDField | **Denormalized** from `DocusafeFolder.family_id` for query convenience (avoids joining folder table on every access-check query). Set automatically at upload time. |
| `is_shared` | BooleanField | Default `False` — `True` when in at least one active temporary share |
| `metadata` | JSONField (default=dict) | Extensible metadata |
| *AuditModel fields* | — | |

**Indexes:** `folder_id`, `family_id`, `mime_type`, `is_shared`

> **Why no `uploaded_by`?** Only the folder owner can upload files, so the uploader is always `DocusafeFolder.owner_id`. Storing it again would be redundant. The `created_by` field from `AuditModel` also records who created the record.

#### `is_shared` Lifecycle (File)

- `True` when file is part of any active `TemporaryFileShare`.
- `False` when file is not in any active temporary share (all deleted/expired/disabled/blocked).
- Updated whenever: share created, file removed from share, share deleted/expired/disabled/blocked.

#### `is_shared` Lifecycle (Folder)

- `True` when **any file** in the folder has `is_shared = True`.
- `False` when **no files** in the folder have `is_shared = True`.
- Updated whenever a file's `is_shared` changes.

#### Allowed File Types

```python
ALLOWED_EXTENSIONS = {
    # Documents
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".odt", ".ods", ".odp", ".txt", ".rtf", ".csv",
    # Images
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp",
    ".heic", ".heif", ".tiff", ".tif", ".ico",
    # Audio
    ".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma",
    # Video
    ".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v",
    # Archives
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2",
    # Other
    ".json", ".xml", ".yaml", ".yml", ".md",
}
```

### 3.4. File Access (`apps/docusafe/models/file_access.py`)

All access grants are **read-only** (view / download). Only the folder owner can upload, update, or delete files.

```
Table: docusafe_file_access
```

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUIDField (PK) | |
| `file_id` | UUIDField | The file being shared |
| `access_type` | CharField — `DocusafeAccessType` | `FAMILY` or `USER` |
| `family_id` | UUIDField | The family context |
| `user_id` | UUIDField (nullable) | Present only when `access_type = USER` |
| `owner_id` | UUIDField | References `UserMaster.id` — the folder owner who created this grant |
| `is_active` | BooleanField | Default `True` |
| *AuditModel fields* | — | |

**Unique constraint:** `(file_id, access_type, family_id, user_id)`
**Indexes:** `file_id`, `access_type`, `family_id`, `user_id`, `owner_id`, `is_active`

#### Sharing Rules

1. **All access is read-only** — shared users can view/download files but cannot modify, delete, or manage anything.
2. **Family-level:** All APPROVED members of the family get read-only access.
3. **User-level:** Specific user gets read-only access. User **must be an APPROVED member** of the owner's family.
4. **Edge case — family already has access:** If file has `FAMILY` access → reject `USER`-level grants for members of that family (redundant).
5. **Upgrade to family:** If individual user grants exist and owner adds `FAMILY` grant → auto-deactivate redundant user-level grants.
6. **Who can grant:** Only the folder owner.

### 3.5. Temporary File Share (`apps/docusafe/models/temporary_share.py`)

A temporary share can contain **multiple files** from across different folders. The share's **UUID (`id`) is used directly** in all URLs and references — no separate token.

```
Table: docusafe_temporary_share
```

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUIDField (PK) | Used as the share identifier in all URLs |
| `password_hash` | CharField(255) | Hashed via `make_password` — **no strength constraints** |
| `title` | `CharField` | Optional title for the share link |
| `status` | `Enum` | [ACTIVE, INACTIVE, EXPIRED, BLOCKED] |
| `expires_at` | `DateTimeField` | Expiration timestamp |
| `file_count` | `IntegerField` | Number of files in share (ReadOnly) |
| `recipient_emails` | `JSONField` | List of recipient emails |
| `view_count` | PositiveIntegerField | Default 0 |
| `failed_attempts` | PositiveIntegerField | Default 0 |
| `max_failed_attempts` | PositiveIntegerField | Default 5 |
| `is_active` | BooleanField | Default `True` |
| `owner_id` | UUIDField | References `UserMaster.id` — the user who created this share |
| `family_id` | UUIDField | References `Family.id` |
| *AuditModel fields* | — | |

**Indexes:** `status`, `expires_at`, `owner_id`, `family_id`

#### Brute-Force Protection

1.  Wrong password → `failed_attempts += 1`.
2.  `failed_attempts >= max_failed_attempts` → `status = BLOCKED`, `is_active = False`.
3.  **Blocked shares are permanently deactivated** — owner can see for 7 days and then deleted by cron.
4.  **Successful access resets** `failed_attempts` to 0.
5.  All attempts (success + failure) logged in `ShareViewLog`.

### 3.6. Temporary Share File (Junction) (`apps/docusafe/models/temporary_share.py`)

```
Table: docusafe_temporary_share_file
```

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUIDField (PK) | |
| `share_id` | UUIDField | References `TemporaryFileShare.id` |
| `file_id` | UUIDField | References `DocusafeFile.id` |
| *TimeAuditModel fields* | — | |

**Unique constraint:** `(share_id, file_id)`
**Indexes:** `share_id`, `file_id`

### 3.7. Share View Log (`apps/docusafe/models/temporary_share.py`)

```
Table: docusafe_share_view_log
```

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUIDField (PK) | |
| `share_id` | UUIDField | References `TemporaryFileShare.id` |
| `success` | BooleanField | `True` = success, `False` = failed |
| `failure_reason` | CharField(100, nullable) | `INVALID_PASSWORD`, `EXPIRED`, `BLOCKED`, `MAX_VIEWS_REACHED`, `DISABLED` |
| `viewed_at` | DateTimeField (auto_now_add) | |
| `ip_address` | GenericIPAddressField | |
| `user_agent` | TextField | |
| `device_type` | CharField(50, nullable) | |
| `device_os` | CharField(100, nullable) | |
| `browser` | CharField(100, nullable) | |
| `country` | CharField(100, nullable) | |
| `city` | CharField(100, nullable) | |
| `client_metadata` | JSONField (default=dict) | |
| *TimeAuditModel fields* | — | |

**Indexes:** `share_id`, `viewed_at`, `ip_address`, `success`

---

## 4. File Path Strategy

### Path Pattern

```
docusafe/<user_id>/<folder_id>/<file_id>_<sanitized_original_filename>
```

**Example:**
```
docusafe/11111111-aaaa-bbbb-cccc-dddddddddddd/22222222-eeee-ffff-0000-111111111111/33333333-4444-5555-6666-777777777777_medical_report.pdf
```

### Rules

-   `file_path` is stored on `DocusafeFile` — the **only** reference to the file in S3.
-   **No pre-signed URLs are stored.** Generated on-the-fly at download (5-minute expiry).
-   File names sanitized: whitespace → underscores, special characters stripped, lowercased.
-   `file_id` prefix guarantees uniqueness.
-   On file deletion: S3 object also deleted (hard delete).
-   On folder deletion: all files deleted from S3 and DB.

### Upload Flow

1.  Client sends `multipart/form-data` POST.
2.  Service validates: auth, family membership, ownership, file type (whitelist), size, folder limits.
3.  Service computes: `mime_type`, `file_size`, `file_extension`, `checksum`.
4.  Service constructs `file_path`, uploads to S3.
5.  Creates `DocusafeFile`, updates folder stats.

### Download Flow

1.  Service verifies access (owner or file access grant).
2.  Generates pre-signed S3 URL (5-minute expiry) from `file_path`.
3.  Returns URL to client.

---

## 5. API Design

All endpoints under `api/v1/docusafe/`. All use `IsAuthenticated` except the public share access endpoint.

### 5.1. Mobile App — Two Main Sections

The mobile app has two primary sections:

| Section | Endpoint | Description |
|---------|----------|-------------|
| **My Safe** | `GET folders/` | Lists the current user's own folders (with file counts, sizes), filtered by `owner_id = user_id` |
| **Shared With Me** | `GET shared-with-me/` | Lists folders containing files shared with the current user (with count of shared files per folder) |

These are the **entry-point endpoints** for the mobile app.

### 5.2. Folder APIs

| Method | Endpoint | View | Description |
|--------|----------|------|-------------|
| GET | `folders/` | `FolderListCreateView` | **My Safe** — list user's own folders (query: `family_id`) |
| POST | `folders/` | `FolderListCreateView` | Create a folder |
| GET | `folders/<folder_id>/` | `FolderDetailUpdateDeleteView` | Folder details |
| PATCH | `folders/<folder_id>/` | `FolderDetailUpdateDeleteView` | Update name, description, remarks |
| DELETE | `folders/<folder_id>/` | `FolderDetailUpdateDeleteView` | Hard-delete + cascades |

### 5.3. File APIs

All file endpoints are **nested under their folder**.

| Method | Endpoint | View | Description |
|--------|----------|------|-------------|
| POST | `folders/<folder_id>/files/` | `FileListUploadView` | Upload file (multipart) |
| GET | `folders/<folder_id>/files/` | `FileListUploadView` | List files in a folder |
| GET | `folders/<folder_id>/files/<file_id>/` | `FileDetailUpdateDeleteView` | File metadata |
| PATCH | `folders/<folder_id>/files/<file_id>/` | `FileDetailUpdateDeleteView` | Update file_name, description, remarks |
| DELETE | `folders/<folder_id>/files/<file_id>/` | `FileDetailUpdateDeleteView` | Hard-delete + cascades |
| GET | `folders/<folder_id>/files/<file_id>/download/` | `FileDownloadView` | Pre-signed S3 URL |
| GET | `folders/<folder_id>/files/<file_id>/shares/` | `FileSharesListView` | List active shares for this file |
| POST | `folders/<folder_id>/files/<file_id>/shares/` | `FileSharesListView` | Create share for this file |

**Upload validation (global platform limits):**
1.  Extension in `ALLOWED_EXTENSIONS` (global constant).
2.  MIME type matches extension.
3.  `file_size <= MAX_FILE_SIZE` (50 MB).
4.  `folder.total_size + file_size <= MAX_FOLDER_SIZE` (500 MB).
5.  `folder.file_count < MAX_FILES_PER_FOLDER` (100).
6.  User owns the folder.

### 5.4. File Sharing APIs

Grant/revoke endpoints are **standalone** (not nested under a single file) since users can select multiple files.

| Method | Endpoint | View | Description |
|--------|----------|------|-------------|
| POST | `access/grant/` | `GrantAccessView` | Grant read-only access to one or more files |
| POST | `access/revoke/` | `RevokeAccessView` | Revoke access grants by IDs |
| GET | `access/file/<file_id>/` | `FileAccessListView` | Who has access to a specific file |
| GET | `shared-with-me/` | `SharedWithMeView` | Folders with files shared with me |
| GET | `shared-with-me/folders/<folder_id>/files/` | `SharedFilesInFolderView` | Shared files in a specific folder |

**Grant access payload (family-level):**
```json
{
    "file_ids": ["uuid1", "uuid2"],
    "access_type": "FAMILY",
    "family_id": "uuid"
}
```

**Grant access payload (user-level):**
```json
{
    "file_ids": ["uuid1", "uuid2"],
    "access_type": "USER",
    "user_ids": ["uuid1", "uuid2"]
}
```

**Revoke access payload:**
```json
{
    "access_ids": ["uuid1", "uuid2"]
}
```

**Validation:**
-   Owner must be the folder owner for all specified files.
-   All access is **read-only**.
-   `FAMILY` → shares with entire family; `USER` → each user must be APPROVED family member.
-   Edge case: if file has `FAMILY` access, reject `USER` grants for that family's members.
-   Upgrading to `FAMILY` auto-deactivates redundant `USER` grants.
-   Revoke: user must be the folder owner of the files referenced by the access grants.

### 5.5. Temporary File Share APIs

| Method | Endpoint | Auth? | View | Description |
|--------|----------|-------|------|-------------|
| GET/POST | `shares/` | ✅ | `TemporarySharesListCreateView` | List user's shares / Create share link |
| GET | `shares/<share_id>/` | ✅ | `TemporaryShareDetailView` | Share details + files + stats |
| PATCH | `shares/<share_id>/` | ✅ | `UpdateTemporaryShareView` | Enable/disable, set new expiry, change password |
| DELETE | `shares/<share_id>/` | ✅ | `DeleteTemporaryShareView` | Delete permanently |
| POST | `shares/<share_id>/files/` | ✅ | `AddFilesToShareView` | Add files to share |
| DELETE | `shares/<share_id>/files/` | ✅ | `RemoveFilesFromShareView` | Remove files from share |
| GET | `shares/<share_id>/views/` | ✅ | `ShareViewLogsView` | View logs |
| POST | `shares/access/<share_id>/` | ❌ | `TemporaryShareAccessView` | **Public** — verify password, get files |

> The `share_id` in all URLs is the `TemporaryFileShare.id` (UUID primary key). No separate token.

**Create payload:**
```json
{
    "file_ids": ["uuid1", "uuid2"],
    "password": "any-password",
    "expires_at": "2026-03-23T18:40:00Z",
    "max_views": 10,
    "max_failed_attempts": 5,
    "recipient_email": "someone@example.com"
}
```

**Public access (`POST shares/access/<share_id>/`):**
```json
{
    "password": "secret123",
    "client_metadata": {
        "screen_resolution": "1920x1080",
        "language": "en-US",
        "timezone": "Asia/Kolkata",
        "app_version": "1.2.0",
        "referrer": "https://whatsapp.com"
    }
}
```

**Processing:**
```
1. Look up share by id (UUID)
2. Check status != EXPIRED and status != BLOCKED
3. Check is_active = True
4. Check expires_at > now()
5. If max_views set → check view_count < max_views
6. Verify password via check_password()

   ON FAILURE (wrong password):
     a. Increment failed_attempts
     b. If failed_attempts >= max_failed_attempts → BLOCKED, is_active = False
     c. Log ShareViewLog (success=False, failure_reason="INVALID_PASSWORD")
     d. Return error with remaining_attempts

   ON FAILURE (other):
     a. Log ShareViewLog (success=False, failure_reason=<reason>)
     b. Return error

   ON SUCCESS:
     a. Increment view_count
     b. Reset failed_attempts to 0
     c. Log ShareViewLog (success=True)
     d. Return file list with pre-signed download URLs
```

**Update payload (PATCH):**
```json
{
    "is_active": true,
    "new_expires_at": "2026-03-25T18:40:00Z",
    "new_password": "newSecret456",
    "max_views": 50
}
```

> **Note:** To extend time, send `new_expires_at` as a full ISO datetime — not a relative offset. Blocked shares cannot be updated.

**Response (success):**
```json
{
    "success": true,
    "data": {
        "files": [
            {
                "file_id": "uuid1",
                "owner_id": "uuid_of_folder_owner",
                "file_name": "medical_report.pdf",
                "file_size": 2048576,
                "mime_type": "application/pdf",
                "download_url": "https://s3.../presigned...",
                "expires_in_seconds": 300
            }
        ],
        "total_files": 1
    }
}
```

---

## 6. Service Layer
#### List Temporary Shares
`GET /v1/docusafe/shares/` (Overview only)

**Response:**
```json
{
    "success": true,
    "data": [
        {
            "id": "share-uuid",
            "title": "Project Docs",
            "status": "ACTIVE",
            "expires_at": "...",
            "view_count": 5,
            "file_count": 3
        }
    ]
}
```

#### Get Share Detail
`GET /v1/docusafe/shares/<id>/` (Full details)

**Response:**
```json
{
    "success": true,
    "data": {
        "id": "share-uuid",
        "title": "Project Docs",
        "status": "ACTIVE",
        "expires_at": "...",
        "view_count": 5,
        "file_count": 3,
        "recipient_emails": ["user1@example.com"],
        "files": [
                {
                    "id": "file-uuid",
                    "file_name": "report.pdf",
                    "file_size": 1024,
                    "mime_type": "application/pdf"
                }
            ]
        }
    ]
}
```

### 6.1. `DocusafeFolderService` (`apps/docusafe/services/folder_service.py`)

- `list_folders(user_id, family_id)` → list folders owned by the user (**My Safe** = `GET folders/`).
- `create_folder(user, family_id, name, **kwargs)` → validate family membership, unique name, create.
- `get_folder(user, folder_id)` → ownership check, return folder.
- `update_folder(user, folder_id, **kwargs)` → ownership check, update.
- `delete_folder(user, folder_id)` → ownership check, cascade delete (see Section 12).
- `recalculate_folder_stats(folder_id)` → recompute `file_count` and `total_size`.

### 6.2. `DocusafeFileService` (`apps/docusafe/services/file_service.py`)

- `upload_file(user, folder_id, file_obj)` → validate (whitelist, size against global constants, count), compute metadata, upload S3, create record, update folder stats.
- `list_files(user, folder_id)` → ownership check, list files.
- `get_file(user, folder_id, file_id)` → ownership or access check, return file.
- `update_file(user, folder_id, file_id, **kwargs)` → ownership check, update.
- `delete_file(user, folder_id, file_id)` → ownership check, cascade delete (see Section 12).
- `get_download_url(user, folder_id, file_id)` → access check, generate pre-signed URL from `file_path`.
- `validate_file_type(filename, content_type)` → whitelist check.
- `compute_file_metadata(file_obj)` → extract size, mime, extension, checksum.
- `update_is_shared(file_id)` → recalculate `is_shared` from active temp shares.

### 6.3. `DocusafeAccessService` (`apps/docusafe/services/access_service.py`)

- `grant_access(granter, file_ids, access_type, family_id, user_ids)` → validate ownership of all files, handle edge cases, bulk-create/upsert.
- `revoke_access(user, access_ids)` → validate ownership, bulk-deactivate grants.
- `get_file_access_list(user, file_id)` → list all grants for a file.
- `has_access(user_id, file_id)` → check ownership, family access, or user access.
- `get_shared_folders(user_id)` → folders containing files shared with user (**Shared With Me**).
- `get_shared_files_in_folder(user_id, folder_id)` → files user has access to in a folder.

### 6.4. `TemporaryShareService` (`apps/docusafe/services/temporary_share_service.py`)

- `create_share(user, file_ids, password, expires_at, max_views, max_failed_attempts, recipient_email)` → create share + junction records, update `is_shared` on files and folders, optionally trigger email.
- `list_shares(user)` → shares created by user.
- `get_share(user, share_id)` → ownership check, return share with files.
- `update_share(user, share_id, **kwargs)` → enable/disable, set new `expires_at`, change password (rejects if blocked).
- `delete_share(user, share_id)` → cascade delete (see Section 12).
- `add_files(user, share_id, file_ids)` → ownership check, add junction records, update `is_shared`.
- `remove_files(user, share_id, file_ids)` → remove junction records, update `is_shared`.
- `get_view_logs(user, share_id)` → ownership check, paginated logs.
- `verify_and_access(share_id, password, request)` → full validation chain, log view, return download URLs.
- `cleanup_expired_shares()` → cron logic.

---

## 7. File Structure

```
apps/docusafe/
├── apps.py
├── models/
│   ├── __init__.py
│   ├── folder.py                     # DocusafeFolder
│   ├── file.py                       # DocusafeFile
│   ├── file_access.py                # DocusafeFileAccess
│   └── temporary_share.py            # TemporaryFileShare, TemporaryShareFile, ShareViewLog
├── serializers/
│   ├── __init__.py
│   ├── folder.py
│   ├── file.py
│   ├── file_access.py
│   └── temporary_share.py
├── services/
│   ├── __init__.py
│   ├── folder_service.py
│   ├── file_service.py
│   ├── access_service.py
│   └── temporary_share_service.py
├── views/
│   ├── __init__.py
│   ├── folder.py                     # Thin — delegates to FolderService
│   ├── file.py                       # Thin — delegates to FileService
│   ├── file_access.py                # Thin — delegates to AccessService
│   └── temporary_share.py            # Thin — delegates to TemporaryShareService
├── urls.py
├── constants.py                      # ALLOWED_EXTENSIONS, default limits
├── migrations/
│   └── ...
├── management/
│   └── commands/
│       └── cleanup_expired_shares.py
└── plan.md
```

---

## 8. URL Routing

```python
# apps/docusafe/urls.py
urlpatterns = [

    # Folders
    path("v1/docusafe/folders/", FolderListCreateView.as_view()),
    path("v1/docusafe/folders/<uuid:folder_id>/", FolderDetailUpdateDeleteView.as_view()),

    # Files
    path("v1/docusafe/folders/<uuid:folder_id>/files/", FileListUploadView.as_view()),
    path("v1/docusafe/folders/<uuid:folder_id>/files/<uuid:file_id>/", FileDetailUpdateDeleteView.as_view()),
    path("v1/docusafe/folders/<uuid:folder_id>/files/<uuid:file_id>/download/", FileDownloadView.as_view()),

    # File Sharing
    path("v1/docusafe/access/grant/", GrantAccessView.as_view()),
    path("v1/docusafe/access/revoke/", RevokeAccessView.as_view()),
    path("v1/docusafe/access/file/<uuid:file_id>/", FileAccessListView.as_view()),
    path("v1/docusafe/shared-with-me/", SharedWithMeView.as_view()),
    path("v1/docusafe/shared-with-me/folders/<uuid:folder_id>/files/", SharedFilesInFolderView.as_view()),

    # Temporary Shares
    path("v1/docusafe/shares/", TemporarySharesListCreateView.as_view()),
    path("v1/docusafe/shares/<uuid:share_id>/", TemporaryShareDetailUpdateDeleteView.as_view()),
    path("v1/docusafe/shares/<uuid:share_id>/files/", ShareFilesManageView.as_view()),
    path("v1/docusafe/shares/<uuid:share_id>/views/", ShareViewLogsView.as_view()),

    # Public Access (No Auth) — uses share UUID directly
    path("v1/docusafe/shares/access/<uuid:share_id>/", TemporaryShareAccessView.as_view()),
]
```

Add to `settings/urls.py`:
```python
if "apps.docusafe" in settings.INSTALLED_APPS:
    urlpatterns.append(path("api/", include("apps.docusafe.urls")))
```

---

## 9. Security

1. **Family membership validation** — in service layer.
2. **Read-only sharing** — shared users can only view/download.
3. **Access checks in services** — not in permission classes.
4. **Password hashing** — `make_password` / `check_password`, no strength constraints.
5. **Rate limiting** — throttle scope `docusafe_share_access: "30/hour"`.
6. **Brute-force** — auto-block after threshold, success resets counter, blocked = permanent.
7. **Pre-signed URLs** — 5-minute expiry, generated on-the-fly.
8. **IP extraction** — handle `X-Forwarded-For`.
9. **File type whitelist** — only `ALLOWED_EXTENSIONS`.
10. **Upload limits** — per-file, per-folder, file count (all enforced via global constants).

---

## 10. Cron Jobs

### `cleanup_expired_shares`

- Schedule: `0 3 * * *` (daily 3 AM UTC).
- **Step 1:** Mark `status = EXPIRED` where `expires_at < now()` and `status = ACTIVE`.
- **Step 2:** Hard-delete shares (+ junction records + view logs) where `expires_at < now() - 7 days` (7-day retention).
- **Step 3:** Recalculate `is_shared` on affected files.
- Uses DB lock via `shared/helpers/crons.py`.

---

## 11. Settings / Config Changes

| File | Change |
|------|--------|
| `settings/urls.py` | Add conditional docusafe URL inclusion |
| `settings/auth.py` | Add throttle scope: `"docusafe_share_access": "30/hour"` |
| `shared/enums/base.py` | Add `DocusafeAccessType`, `TemporaryShareStatus` |
| `settings/crons.py` | Add `cleanup_expired_shares` cron |
| `requirements/base.txt` | Add `user-agents` library |
| `apps/docusafe/constants.py` | Limits + allowed extensions |

### Constants (`constants.py`)

```python
# Global platform limits (not per-folder)
MAX_FILE_SIZE = 50 * 1024 * 1024               # 50 MB per file
MAX_FOLDER_SIZE = 500 * 1024 * 1024             # 500 MB per folder
MAX_FILES_PER_FOLDER = 100

# Temporary share defaults
DEFAULT_MAX_FAILED_ATTEMPTS = 5
PRESIGNED_URL_EXPIRY_SECONDS = 300              # 5 minutes
EXPIRED_SHARE_RETENTION_DAYS = 7

# Allowed file extensions (whitelist)
ALLOWED_EXTENSIONS = { ... }
```

---

## 12. Deletion Cascade Summary

Manual cascade in service layer (no FKs):

| When deleting... | Also delete/update... |
|------------------|----------------------|
| **Folder** | All files (S3 + DB), all `DocusafeFileAccess` for those files, remove files from `TemporaryShareFile` junctions, update `is_shared` on files and folder, delete folder |
| **File** | S3 object, all `DocusafeFileAccess`, remove from `TemporaryShareFile` junctions, update `is_shared` on file and parent folder, update folder stats, delete file |
| **Temporary Share** | `TemporaryShareFile` junctions, `ShareViewLog` records, update `is_shared` on affected files + parent folders |
| **Expired shares (cron)** | Same as share deletion, after 7-day retention |
| **File removed from share** | Delete junction record, update `is_shared` on file + parent folder |

---

## 13. Resolved Questions

| # | Question | Decision |
|---|----------|----------|
| 1 | Default limits | 50 MB/file, 500 MB/folder, 100 files — **global platform constants**, not per-folder |
| 2 | Failed attempts reset | Yes — success resets to 0 |
| 3 | Expired share retention | 7 days |
| 4 | Folder delete confirmation | Not needed — frontend handles |
| 5 | Multiple shares per file | Yes |
| 6 | Cascade handling | Manual in service layer |
| 7 | Access scope | File-level only, read-only |
| 8 | Password strength | No constraints |
| 9 | Sharing scope | Family-wide or per-user (must be family member) |
| 10 | Temp share scope | Multi-file, managed via CRUD |
| 11 | Permission classes | `IsAuthenticated` only |
| 12 | Email notification | Optional `recipient_email` |
| 13 | Share identifier | UUID primary key — no separate token |
| 14 | File path pattern | `docusafe/user_id/folder_id/file_id_filename` |
| 15 | Service layer | Modular — views thin, logic in services |
| 16 | Extend time | Client sends `new_expires_at` (ISO datetime), not relative offset |
| 17 | Redundant fields | No `uploaded_by` on file (owner is folder owner); `family_id` on file is denormalized |

---

## 14. Implementation Order

1. **Phase 1 — Models & Migrations** — Enums, AppConfig, all 6 models, migrations
2. **Phase 2 — Constants** — `constants.py` (allowed extensions, limits)
3. **Phase 3 — Folder CRUD** — `FolderService`, serializers, thin views, URLs, My Safe endpoint
4. **Phase 4 — File Management** — `FileService`, upload (whitelist), list, detail, download, deletion, S3 integration
5. **Phase 5 — File Sharing** — `AccessService`, grant/revoke (family + user), Shared With Me endpoints
6. **Phase 6 — Temporary Shares** — `TemporaryShareService`, create (multi-file), manage files, public access, view logging, brute-force, `is_shared`
7. **Phase 7 — Cron & Wiring** — Cleanup command, cron registration, URL wiring, throttle scope
8. **Phase 8 — Bruno Collection** — API documentation
9. **Phase 9 — Playwright Tests** — Full end-to-end API tests in `tests/playwright/` covering:
   - Folder CRUD (create, list, detail, update, delete + cascade)
   - File upload (valid types, blocked types, size limits, folder limits), list, detail, update, delete
   - Download (owner, shared user, unauthorized)
   - File sharing — grant family access, grant user access, revoke, edge cases (family→user rejection, upgrade to family)
   - My Safe and Shared With Me endpoints
   - Temporary shares — create (multi-file), add/remove files, update, delete, view logs
   - Public access — correct password, wrong password, brute-force block, expired, disabled, max views
   - `is_shared` flag tracking
   - Cascade deletion verification (folder delete cascades, file delete cascades)
