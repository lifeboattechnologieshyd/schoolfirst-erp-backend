# ruff: noqa

from .base import *  # noqa : F403

SILKY_PYTHON_PROFILER = True
SILKY_INTERCEPT_PERCENT = 100
SILKY_META = True

if ENABLE_SILK:
    INSTALLED_APPS += ["silk"]
    MIDDLEWARE += ["silk.middleware.SilkyMiddleware"]
