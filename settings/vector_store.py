from shared.utils import get_from_env

#####################################
#       Vector Store Settings        #
#####################################

# --- Qdrant Settings ---
QDRANT_HOST = get_from_env("QDRANT_HOST", "localhost")
QDRANT_PORT = get_from_env("QDRANT_PORT", 6333, type_cast=int)
QDRANT_GRPC_PORT = get_from_env("QDRANT_GRPC_PORT", 6334, type_cast=int)
QDRANT_API_KEY = get_from_env("QDRANT_API_KEY", None, optional=True)
QDRANT_URL = get_from_env("QDRANT_URL", None, optional=True)  # Full URL for Qdrant Cloud
QDRANT_COLLECTION = get_from_env("QDRANT_COLLECTION", "docusafe_files")

# --- Embedding Settings ---
EMBEDDING_PROVIDER = get_from_env("EMBEDDING_PROVIDER", "AWS_BEDROCK")
AWS_BEDROCK_EMBEDDING_MODEL_ID = get_from_env("AWS_BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")
AWS_BEDROCK_EMBEDDING_DIMENSIONS = get_from_env("AWS_BEDROCK_EMBEDDING_DIMENSIONS", 1024, type_cast=int)
AWS_BEDROCK_EMBEDDING_REGION = get_from_env("AWS_BEDROCK_EMBEDDING_REGION", "us-east-1")

# AWS credentials for Bedrock/Textract (separate from S3/MinIO credentials)
AWS_BEDROCK_EMBEDDING_ACCESS_KEY_ID = get_from_env("AWS_BEDROCK_EMBEDDING_ACCESS_KEY_ID", None, optional=True)
AWS_BEDROCK_EMBEDDING_SECRET_ACCESS_KEY = get_from_env("AWS_BEDROCK_EMBEDDING_SECRET_ACCESS_KEY", None, optional=True)

# --- Textract Settings ---
AWS_BEDROCK_EMBEDDING_TEXTRACT_REGION = get_from_env("AWS_BEDROCK_EMBEDDING_TEXTRACT_REGION", "ap-south-1")
