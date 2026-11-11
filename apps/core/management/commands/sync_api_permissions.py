import ast
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Modules, Permissions

MODULE_PREFIX_MAPPING = {
    "school": "School Management",
    "organization": "School Management",
    "branch": "School Management",

    "student": "Student Management",

    "student_document": "Document Management",
    "school_document": "Document Management",
    "school_document_type": "Document Management",
    "staff.document": "Document Management",
    "vehicle.document": "Document Management",

    "grade": "Class & Section Management",
    "section": "Class & Section Management",
    "room": "Class & Section Management",

    "transport": "Transport Management",
    "transport_fee_rule": "Transport Management",
    "route": "Transport Management",
    "stop": "Transport Management",
    "trip": "Transport Management",
    "vehicle": "Transport Management",

    "homework": "Homework Management",
    "assignment": "Homework Management",

    "examination": "Exam Management",
    "hall_ticket": "Exam Management",
    "report_card": "Exam Management",

    "fee_collection_plan": "Fee Management",
    "fee_concession": "Fee Management",
    "fee_installment": "Fee Management",
    "fee_installment_item": "Fee Management",
    "fee_plan": "Fee Management",
    "fee_plan_installment": "Fee Management",
    "fee_template": "Fee Management",
    "fee_template_item": "Fee Management",
    "fee_type": "Fee Management",
    "late_fee_rule": "Fee Management",
    "student_fee": "Fee Management",

    "timetable": "Time Table",
    "timetable_period": "Time Table",
    "timetable_term": "Time Table",
    "teacher_schedule": "Time Table",
    "substitution": "Time Table",

    "student_attendance": "Attendance",
    "staff_attendance": "Attendance",
    "student_leave": "Attendance",
    "staff_leave": "Attendance",

    "bulletin": "Communication Management",
    "parent_teacher_meeting": "Communication Management",
    "ptm": "Communication Management",

    "academic_calendar": "Academic Calendar",
    "calendar": "Academic Calendar",

    "gallery": "Gallery",
    "feedback": "Feedback",

    "staff": "Staff Management",
    "user": "Staff Management",

    "remark": "Remarks",

    "academic_year": "Academic Setup",
    "grade_configuration": "Academic Setup",
    "subject": "Academic Setup",
}


def get_module_name(permission_name):
    """
    Resolve a permission to an existing production module.

    Uses the longest matching prefix to handle nested permissions.
    """

    matching_prefixes = [
        prefix
        for prefix in MODULE_PREFIX_MAPPING
        if (
            permission_name == prefix
            or permission_name.startswith(prefix + ".")
        )
    ]

    if not matching_prefixes:
        return None

    longest_prefix = max(matching_prefixes, key=len)

    return MODULE_PREFIX_MAPPING[longest_prefix]


class Command(BaseCommand):

    help = "Sync API permissions into existing production modules"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview permissions without saving them",
        )

    def handle(self, *args, **options):

        dry_run = options["dry_run"]

        self.stdout.write(
            self.style.SUCCESS("Starting API permission synchronization...")
        )

        # Step 1: Scan installed application files
        permissions_found = set()

        for app_config in apps.get_app_configs():

            app_path = Path(app_config.path)

            for file_path in app_path.rglob("*.py"):

                if "migrations" in file_path.parts:
                    continue

                try:
                    source = file_path.read_text(encoding="utf-8")
                    tree = ast.parse(source)

                except (OSError, UnicodeDecodeError, SyntaxError):
                    continue

                for node in ast.walk(tree):

                    if not isinstance(node, ast.ClassDef):
                        continue

                    for class_node in node.body:

                        if not isinstance(class_node, ast.Assign):
                            continue

                        for target in class_node.targets:

                            if (
                                isinstance(target, ast.Name)
                                and target.id == "required_permission"
                                and isinstance(class_node.value, ast.Constant)
                                and isinstance(class_node.value.value, str)
                            ):
                                permissions_found.add(
                                    class_node.value.value.strip()
                                )

        self.stdout.write(
            f"Scanned permissions: {len(permissions_found)}"
        )

        # Step 2: Map permissions to existing modules
        mapped_permissions = {}
        unmapped_permissions = []

        for permission_name in sorted(permissions_found):

            module_name = get_module_name(permission_name)

            if not module_name:
                unmapped_permissions.append(permission_name)
                continue

            mapped_permissions[permission_name] = module_name

        # Step 3: Validate all module names before syncing
        required_module_names = set(mapped_permissions.values())

        existing_modules = {
            module.module_name: module
            for module in Modules.objects.filter(
                module_name__in=required_module_names
            )
        }

        missing_modules = (
            required_module_names - set(existing_modules.keys())
        )

        if missing_modules:
            raise CommandError(
                "These modules do not exist in production: "
                + ", ".join(sorted(missing_modules))
                + ". No permissions were created."
            )

        # Step 4: Display mapping
        self.stdout.write("\nPermission mapping:")

        for permission_name, module_name in sorted(
            mapped_permissions.items()
        ):
            self.stdout.write(
                f"{permission_name} -> {module_name}"
            )

        if unmapped_permissions:
            self.stdout.write(
                self.style.WARNING("\nUnmapped permissions:")
            )

            for permission_name in unmapped_permissions:
                self.stdout.write(f"  {permission_name}")

        # Step 5: Dry run
        if dry_run:

            self.stdout.write(
                self.style.WARNING(
                    "\nDRY RUN: No database changes were made."
                )
            )

            return

        # Step 6: Create missing permissions under existing modules
        created_count = 0
        existing_count = 0

        for permission_name, module_name in sorted(
            mapped_permissions.items()
        ):

            module = existing_modules[module_name]

            permission, created = Permissions.objects.get_or_create(
                module=module,
                permission_name=permission_name,
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created: {permission_name} -> {module_name}"
                    )
                )

            else:
                existing_count += 1

        # Step 7: Summary
        self.stdout.write("\nSynchronization completed.")

        self.stdout.write(f"Total discovered: {len(permissions_found)}")
        self.stdout.write(f"Mapped: {len(mapped_permissions)}")
        self.stdout.write(f"Unmapped: {len(unmapped_permissions)}")
        self.stdout.write(f"Created: {created_count}")
        self.stdout.write(f"Already existing: {existing_count}")