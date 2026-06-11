
from apps.core.models import Roles, UserRoles, UserMaster
from shared.enums.roles import RolesEnum


def get_or_create_parent(mobile_number):

    print("=" * 50)
    print("get_or_create_parent() called")
    print("Mobile Number :", mobile_number)

    if not mobile_number:
        print("No mobile number")
        return None

    mobile_number = str(mobile_number).strip()

    print("Searching UserMaster...")

    user = UserMaster.objects.filter(
        mobile_number=mobile_number,
    ).first()

    print("User :", user)

    if user is None:

        print("Creating UserMaster...")

        user = UserMaster.objects.create(
            username=mobile_number,
            mobile_number=mobile_number,
        )

        print("User created :", user.id)

    print("Getting Parent Role...")

    parent_role = Roles.objects.filter(
        role_name=RolesEnum.PARENT,
    ).first()

    print("Parent Role :", parent_role)

    print("Creating UserRole...")

    UserRoles.objects.get_or_create(
        user=user,
        role=parent_role,
    )

    print("UserRole Created")

    return user