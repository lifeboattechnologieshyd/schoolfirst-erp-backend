from django.db import transaction
from django.utils import timezone

from apps.transport.models import LiveLocation, LocationHistory


def update_live_location(
    school,
    trip,
    latitude,
    longitude,
    speed=0,
    heading=None,
    altitude=None,
    accuracy=None,
    source=LiveLocation.LocationSource.MOBILE,
    device_timestamp=None,
):

    with transaction.atomic():

        live_location, _ = LiveLocation.objects.update_or_create(
            trip=trip,
            defaults={
                "school": school,
                "latitude": latitude,
                "longitude": longitude,
                "speed": speed,
                "heading": heading,
                "altitude": altitude,
                "accuracy": accuracy,
                "source": source,
                "device_timestamp": device_timestamp,
                "recorded_at": timezone.now(),
            },
        )

        LocationHistory.objects.create(
            school=school,
            branch=trip.branch,
            trip=trip,
            latitude=latitude,
            longitude=longitude,
            speed=speed,
            heading=heading,
            altitude=altitude,
            accuracy=accuracy,
            source=source,
            device_timestamp=device_timestamp,
            recorded_at=live_location.recorded_at,
        )

        return live_location