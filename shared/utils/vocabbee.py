from apps.vocabbee.models import KidWordProgress, Words


def get_practice_words(kid, grade, no_of_questions=10):

    attempted_word_ids = KidWordProgress.objects.filter(
        kid=kid
    ).values_list(
        "word_id",
        flat=True
    )

    selected_words = list(
        Words.objects.filter(
            grade=grade,
            is_active=True,
            voice_status="GENERATED",
            is_valid=True
        ).select_related(
            "audio"
        ).exclude(
            id__in=attempted_word_ids
        ).order_by("?")[:no_of_questions]
    )

    if len(selected_words) < no_of_questions:

        remaining_count = no_of_questions - len(selected_words)

        selected_word_ids = [
            word.id for word in selected_words
        ]

        additional_words = list(
            Words.objects.filter(
                grade=grade,
                is_active=True,
                voice_status="GENERATED",
                is_valid=True
            ).select_related(
                "audio"
            ).exclude(
                id__in=attempted_word_ids
            ).exclude(
                id__in=selected_word_ids
            ).order_by("?")[:remaining_count]
        )

        selected_words.extend(additional_words)

    response = []

    for word in selected_words:

        audio = getattr(word, "audio", None)

        response.append({

            "word_id": str(word.id),
            "word": word.word,

            # Existing fields
            "meaning": word.meaning,
            "part_of_speech": word.part_of_speech,
            "origin": word.origin,
            "usage": word.usage,
            "subject": word.subject,
            "concept": word.concept,
            "hint": word.hint,
            "difficulty": word.difficulty,

            # New word fields
            "root_word": word.root_word,
            "phonetic_script": word.phonetic_script,
            "syllabified_stressed_transcript": (
                word.syllabified_stressed_transcript
            ),
            "origin_word": word.origin_word or None,
            "origin_word_meaning": word.origin_word_meaning or None,
            "antonym": word.antonym or None,
            "synonym": word.synonym or None,
            "points": word.points,
            "word_status": word.word_status,
            "domain": word.domain,

            # Seven audio URLs
            "pronunciation_audio_url": (
                audio.pronunciation_audio_url if audio else None
            ),
            "meaning_audio_url": (
                audio.meaning_audio_url if audio else None
            ),
            "part_of_speech_audio_url": (
                audio.part_of_speech_audio_url if audio else None
            ),
            "origin_audio_url": (
                audio.origin_audio_url if audio else None
            ),
            "usage_audio_url": (
                audio.usage_audio_url if audio else None
            ),
            "phonetic_script_audio_url": (
                audio.phonetic_script_audio_url if audio else None
            ),
            "syllabified_stressed_transcript_audio_url": (
                audio.syllabified_stressed_transcript_audio_url
                if audio else None
            )
        })

    return response