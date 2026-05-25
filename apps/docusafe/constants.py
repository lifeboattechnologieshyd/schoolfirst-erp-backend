"""
Docusafe — Global Platform Constants

These are platform-level limits enforced uniformly for every folder/file.
They are NOT stored per-folder; they live here as the single source of truth.
"""

# ---------------------------------------------------------------------------
# File & folder size limits
# ---------------------------------------------------------------------------
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB per file
MAX_FOLDER_SIZE = 500 * 1024 * 1024  # 500 MB total per folder
MAX_FILES_PER_FOLDER = 100  # Maximum number of files in a single folder

# ---------------------------------------------------------------------------
# Temporary share defaults
# ---------------------------------------------------------------------------
DEFAULT_MAX_FAILED_ATTEMPTS = 5  # Block share after this many wrong passwords
PRESIGNED_URL_EXPIRY_SECONDS = 300  # 5-minute pre-signed URL lifetime (temporary shares)
FILE_RETRIEVE_URL_EXPIRY_SECONDS = 900  # 15-minute pre-signed URL lifetime (file retrieve endpoint)
EXPIRED_SHARE_RETENTION_DAYS = 7  # Days to keep expired/blocked shares before hard-delete
MAX_SHARE_CLIENT_METADATA_BYTES = 2 * 1024  # Cap logged client metadata to 2 KB per request

# ---------------------------------------------------------------------------
# Allowed file extensions (whitelist)
# Only files with these extensions may be uploaded.
# NOTE: .odt, .ods, .odp, .rtf removed — legacy formats no longer accepted.
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {
        # Documents
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".txt",
        ".csv",
        # Images
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".svg",
        ".webp",
        ".heic",
        ".heif",
        ".tiff",
        ".tif",
        ".ico",
        # Audio
        ".mp3",
        ".wav",
        ".aac",
        ".flac",
        ".ogg",
        ".m4a",
        ".wma",
        # Video
        ".mp4",
        ".avi",
        ".mov",
        ".mkv",
        ".wmv",
        ".flv",
        ".webm",
        ".m4v",
        # Archives
        ".zip",
        ".rar",
        ".7z",
        ".tar",
        ".gz",
        ".bz2",
        # Other
        ".json",
        ".xml",
        ".yaml",
        ".yml",
        ".md",
    }
)

# ---------------------------------------------------------------------------
# Embedding & text extraction
# ---------------------------------------------------------------------------

# Extensions supported for text extraction → embedding pipeline
EMBEDDABLE_EXTENSIONS: frozenset[str] = frozenset(
    {
        # Documents (structured parsers)
        ".pdf",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        # Plain text documents (read directly)
        ".txt",
        ".csv",
        ".md",
        # Structured data (preserve key/value structure)
        ".json",
        ".xml",
        ".yaml",
        ".yml",
        # Images — OCR via Textract (Textract-supported formats only)
        ".jpg",
        ".jpeg",
        ".png",
        ".tiff",
        ".tif",
        ".bmp",
    }
)

# Extensions that can be read as plain text (no Textract)
PLAIN_TEXT_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".txt",
        ".csv",
        ".md",
    }
)

# Structured document formats with dedicated Python parsers
STRUCTURED_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".docx",
        ".xlsx",
        ".xls",
        ".pptx",
        ".ppt",
    }
)

# Data interchange formats — structure-preserving parsing
STRUCTURED_DATA_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".json",
        ".xml",
        ".yaml",
        ".yml",
    }
)

# Image formats eligible for OCR embedding (Textract-supported only)
OCR_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".tiff",
        ".tif",
        ".bmp",
    }
)

# Per-file limits for the embedding pipeline
EMBEDDING_MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
EMBEDDING_MAX_PAGES = 100

# Textract sync API limit (single-page docs only, max 5 MB)
TEXTRACT_SYNC_MAX_SIZE = 5 * 1024 * 1024  # 5 MB

# Semantic chunking parameters (used by SemanticChunker)
SEMANTIC_CHUNK_MAX_SIZE = 1500  # max characters per semantic chunk
SEMANTIC_CHUNK_MIN_SIZE = 200  # min characters (merge if smaller)
SEMANTIC_CHUNK_OVERLAP = 100  # overlap for character-level fallback splits
