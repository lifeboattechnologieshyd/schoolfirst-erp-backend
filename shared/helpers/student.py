
from apps.core.models import Roles, UserRoles, UserMaster
from shared.enums.roles import RolesEnum


def get_or_create_parent(mobile):

    print("=" * 60)
    print("get_or_create_parent() called")
    print("Received Mobile :", mobile)

    if not mobile:
        print("Mobile number is empty.")
        return None

    mobile = str(mobile).strip()

    print("Mobile after strip :", mobile)

    print("Searching UserMaster...")

    user = UserMaster.objects.filter(
        mobile=mobile,
    ).first()

    print("User Found :", user)

    if user is None:

        print("User does not exist.")
        print("Creating UserMaster...")

        user = UserMaster.objects.create(
            username=mobile,
            mobile=mobile,
        )

        print("UserMaster Created Successfully.")
        print("User ID :", user.id)

    else:

        print("Existing User ID :", user.id)

    print("Fetching Parent Role...")

    parent_role = Roles.objects.filter(
        role_name=RolesEnum.PARENT,
    ).first()

    print("Parent Role :", parent_role)

    if parent_role is None:

        print("PARENT role not found in Roles table.")

        raise Exception(
            "PARENT role not found."
        )

    print("Assigning PARENT role...")

    user_role, created = UserRoles.objects.get_or_create(
        user=user,
        role=parent_role,
    )

    print("UserRole :", user_role)

    if created:

        print("PARENT role assigned successfully.")

    else:

        print("User already has PARENT role.")

    print("Returning User :", user.id)
    print("=" * 60)

    return user