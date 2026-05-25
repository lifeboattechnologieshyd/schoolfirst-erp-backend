from django.conf import settings


class AppRouter:
    """
    Route DB operations based on app -> db mapping in settings.APP_TO_DB_MAPPING
    """

    def db_for_read(self, model, **hints):
        return settings.APP_TO_DB_MAPPING.get(model._meta.app_label, "default")

    def db_for_write(self, model, **hints):
        return settings.APP_TO_DB_MAPPING.get(model._meta.app_label, "default")

    def allow_relation(self, obj1, obj2, **hints):
        db1 = settings.APP_TO_DB_MAPPING.get(obj1._meta.app_label, "default")
        db2 = settings.APP_TO_DB_MAPPING.get(obj2._meta.app_label, "default")
        return db1 == db2

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        target_db = settings.APP_TO_DB_MAPPING.get(app_label, "default")
        return db == target_db
