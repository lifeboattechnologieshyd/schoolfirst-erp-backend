import structlog

application_logger = structlog.get_logger("application")

payment_logger = structlog.get_logger("payment")

auth_logger = structlog.get_logger("auth")

audit_logger = structlog.get_logger("audit")

scheduler_logger = structlog.get_logger("scheduler")