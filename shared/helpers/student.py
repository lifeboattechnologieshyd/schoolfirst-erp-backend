
from apps.core.models import Roles, UserRoles, UserMaster
from shared.enums.roles import RolesEnum


def get_or_create_parent(mobile_number):

    if not mobile_number:
        return None

    mobile_number = str(mobile_number).strip()

    user = UserMaster.objects.filter(
        mobile_number=mobile_number,
    ).first()

    if user is None:

        user = UserMaster.objects.create(
            username=mobile_number,
            mobile_number=mobile_number,
        )

    parent_role = Roles.objects.get(
        role_name=RolesEnum.PARENT,
    )

    UserRoles.objects.get_or_create(
        user=user,
        role=parent_role,
    )

    return user