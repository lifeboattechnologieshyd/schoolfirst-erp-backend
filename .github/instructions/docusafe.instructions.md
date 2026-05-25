---
description: "Use when working in the docusafe app: file/folder CRUD, access control, temporary sharing, hybrid semantic search, vector embeddings, or document workflows."
applyTo: "apps/docusafe/**"
---

# Docusafe App Conventions

## Session Close-Out

After Python code changes, follow the repo-level close-out validation in [AGENTS.md](../../AGENTS.md). Run `source ~/.zshrc && source .venv/bin/activate && ruff check . --output-format concise && ty check` from the repo root, and fix any failures before handoff.

## URL Structure

Docusafe follows a **nested URL hierarchy** (folders → files):

```
v1/docusafe/folders/                      # folder CRUD
v1/docusafe/folders/{id}/files/           # file CRUD within folder
v1/docusafe/folders/{id}/files/bulk/      # batch upload
v1/docusafe/access/grant|revoke/          # access management
v1/docusafe/shared-with-me/              # shared files view
v1/docusafe/shares/                       # temporary share CRUD
v1/docusafe/shares/access/{id}/           # public — AllowAny
v1/docusafe/search/                       # hybrid search
```

When adding new file-level endpoints, nest them under the folder URL.

## Access Control

Access is managed at two levels via `DocusafeAccessType` (from `shared/enums/base.py`):
- **Family-level**: entire family group has access
- **User-level**: individual user access

`DocusafeFileAccess` model stores grants. Use `access_service.py` for grant/revoke operations — never manipulate access records directly in views.

## Public Endpoints

Temporary share access and download endpoints are **public** (`AllowAny`). Always declare this explicitly:

```python
permission_classes = [AllowAny]
```

Do **not** assume default permissions apply to these endpoints.

## Hybrid Search

`DocusafeSearchView` combines:
- **Semantic search**: vector embeddings via `vector_search_service.py` → Qdrant
- **Sparse search**: BM25 keyword matching

Both results are merged and ranked. The embeddings are generated via AWS Bedrock (`bedrock_embeddings.py` in `shared/clients/`).

When adding new searchable content, ensure:
1. Embeddings are generated on file upload/update (via `embedding_service.py`)
2. Qdrant vectors are stored/updated in `vector_store_service.py`
3. Textract-parsed text is indexed (via `textract_service.py`)

## Services Map

| Service | Responsibility |
|---------|---------------|
| `file_service.py` | File CRUD, metadata |
| `folder_service.py` | Folder hierarchy |
| `file_storage_service.py` | S3-compatible object storage (upload/download/delete) |
| `access_service.py` | Permission grants/revokes |
| `share_access_service.py` | Temporary share lifecycle |
| `embedding_service.py` | Vector embeddings via Bedrock |
| `vector_store_service.py` | Qdrant reads/writes |
| `vector_search_service.py` | Hybrid search orchestration |
| `textract_service.py` | AWS Textract document parsing |
| `bulk_upload_service.py` | Batch upload with queue |

## Key Pitfalls

- Do **not** bypass `access_service.py` to check permissions inline in views — service handles the logic.
- Temporary share download endpoints are public; confirm `AllowAny` is explicit, not inherited.
- Bulk upload dispatches to a queue (async) — do **not** assume synchronous completion in the view response.
- Cross-app references to docusafe files from the assistant use a `docusafe_file_ids` list on `Thread.module_settings` — not a FK.
