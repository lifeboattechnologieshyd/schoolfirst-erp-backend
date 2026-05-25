#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys

# from .tracing import init_tracer
from dotenv import load_dotenv

load_dotenv()


def main():
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.development")

    print("############################ DATABASES ############################")  # noqa: T201
    print(f"PostgreSQL: {os.environ.get('POSTGRES_DB_NAME')}")  # noqa: T201
    print("###################################################################")  # noqa: T201

    # try:
    #     ENABLE_TRACING = os.environ.get('ENABLE_TRACING', 'False')
    #     if ENABLE_TRACING == "True":
    #         init_tracer()
    # except:
    #     pass

    try:
        from django.core.management import execute_from_command_line  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
