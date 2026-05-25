def has_attached_urls(
    *,
    media_urls: list[str] | None,
    youtube_url: str | None,
    external_urls: list[str] | None,
) -> bool:
    return bool(media_urls or youtube_url or external_urls)


def has_body_text(text: str | None) -> bool:
    return bool(text and str(text).strip())


def validate_feed_content(
    *,
    body_text: str | None,
    media_urls: list[str] | None,
    youtube_url: str | None,
    external_urls: list[str] | None,
) -> dict[str, str] | None:
    media_urls = media_urls or []
    external_urls = external_urls or []

    if youtube_url and media_urls:
        return {"media_urls": "media_urls must be empty for youtube posts"}

    if not has_attached_urls(
        media_urls=media_urls,
        youtube_url=youtube_url,
        external_urls=external_urls,
    ) and not has_body_text(body_text):
        return {
            "body_text": (
                "body_text is required when media_urls, youtube_url, and external_urls are all empty."
            )
        }

    return None
