from dataclasses import dataclass

from apps.core.models.user import UserMaster


@dataclass(frozen=True)
class UserLookupResult:
    id: str
    email: str
    first_name: str | None
    last_name: str | None
    gender: str | None
    profile_image: str | None

    def to_response_data(self) -> dict[str, str | None]:
        return {
            "id": self.id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "gender": self.gender,
            "profile_image": self.profile_image,
        }


class UserLookupService:
    @staticmethod
    def get_by_email(email: str) -> UserLookupResult | None:
        """
        Lookup a user by email.
        Returns a typed user summary or None.
        """
        user = UserMaster.objects.filter(email__iexact=email, is_active=True).first()
        if not user:
            return None
        return UserLookupResult(
            id=str(user.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            gender=user.gender,
            profile_image=str(user.profile_image) if user.profile_image else None,
        )
