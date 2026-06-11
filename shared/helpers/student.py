
from apps.core.models import Roles, UserRoles, UserMaster
from shared.enums.roles import RolesEnum


def get_or_create_parent(mobile_number):

    print("=" * 50)
    print("get_or_create_parent() called")
    print("Mobile Number :", mobile_number)

    if not mobile_number:
        print("Mobile number is empty.")
        return None

    mobile_number = str(mobile_number).strip()

    user = UserMaster.objects.filter(
        mobile_number=mobile_number,
    ).first()

    if user:

        print("Existing user found :", user.id)

    else:

        print("Creating new parent user...")

        user = UserMaster.objects.create(
            username=mobile_number,
            mobile_number=mobile_number,
        )

        print("Parent user created :", user.id)

    parent_role = Roles.objects.get(
        role_name=RolesEnum.PARENT,
    )

    UserRoles.objects.get_or_create(
        user=user,
        role=parent_role,
    )

    print("Parent role assigned.")
    print("=" * 50)

    return user