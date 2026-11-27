from django.db import transaction, IntegrityError
from django.db.models import Count
from django.utils import timezone
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
import os
import requests
from django.core.paginator import Paginator

import random
from datetime import timedelta
from io import BytesIO
from urllib.parse import urlparse

from apps.core.models import UserMaster
from apps.vocabbee.models import Grades, Words, WordAudios, PracticeAttempts, Subjects, Tournaments, Devices, \
    TournamentGrades, TournamentQuestions, TournamentParticipants
from shared.mixins import CustomResponse
from shared.permissions import HasPermission
from shared.utils.s3 import save_to_s3


class GradesList(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permissions = {"GET": "vocabbee.grade.view", "POST": "vocabbee.grade.create",
                            "PUT": "vocabbee.grade.update", "DELETE": "vocabbee.grade.delete"}

    def get(self, request):

        grades = Grades.objects.filter(
            is_active=True
        ).order_by(
            "sort_order"
        )

        response = []

        for grade in grades:

            response.append({
                "grade_id": str(grade.id),
                "name": grade.name
            })

        return CustomResponse().successResponse(
            data=response,
            description="Grades fetched successfully"
        )

    def post(self, request):
        if not request.user.is_admin:
            return CustomResponse().errorResponse(
                data={},
                description="Unauthorized"
            )
        name = request.data.get("name")
        sort_order = request.data.get("sort_order", 1)
        if not name:
            return CustomResponse().errorResponse(
                data={},
                description="Grade name is required"
            )
        grade = Grades.objects.create(
            name=name,
            sort_order=sort_order
        )
        return CustomResponse().successResponse(
            data={
                "grade_id": str(grade.id)
            },
            description="Grade created successfully"
        )
    def put(self, request):
        if not request.user.is_admin:
            return CustomResponse().errorResponse(
                data={},
                description="Unauthorized"
            )

        grade_id = request.data.get("grade_id")

        grade = Grades.objects.filter(
            id=grade_id,
            is_active=True
        ).first()
        if not grade:
            return CustomResponse().errorResponse(
                data={},
                description="Invalid grade"
            )
        name = request.data.get("name")
        sort_order = request.data.get("sort_order")
        if not name:
            return CustomResponse().errorResponse(
                data={},
                description="Grade name is required"
            )
        grade.name = name
        if sort_order is not None:
            grade.sort_order = sort_order
        grade.save()
        return CustomResponse().successResponse(
            data={
                "grade_id": str(grade.id)
            },
            description="Grade updated successfully"
        )

    def delete(self, request):
        if not request.user.is_admin:
            return CustomResponse().errorResponse(
                data={},
                description="Unauthorized"
            )
        grade_id = request.data.get("grade_id")
        grade = Grades.objects.filter(
            id=grade_id,
            is_active=True
        ).first()
        if not grade:
            return CustomResponse().errorResponse(
                data={},
                description="Invalid grade"
            )
        grade.is_active = False
        grade.save()
        return CustomResponse().successResponse(
            data={},
            description="Grade deleted successfully"
        )
import pandas as pd


def download_file_from_s3(url, word):
    audio_response = requests.get(url)
    audio_response.raise_for_status()
    audio_file = BytesIO(audio_response.content)
    filename = os.path.basename(urlparse(url).path)
    audio_file.name = filename
    return save_to_s3(
        path="words",
        file_obj=audio_file
    )

# def getWordAudio(word: Words):
#     data = import_word_from_schoolfirst(word.word)
#     if not data:
#         # todo- we have to use google ai or tts to generate audio
#         return False, "No Word found in SchoolFirst"
#     pronunciation_audio_url = data["pronunciation_audio"]
#     meaning_audio_url = data["meaning_audio"]
#     part_of_speech_audio_url = data["part_of_speech_audio"]
#     origin_audio_url = data["origin_audio"]
#     usage_audio_url = data["usage_audio"]
#     p_a_u = download_file_from_s3(pronunciation_audio_url, word)
#     m_a_u = download_file_from_s3(meaning_audio_url, word)
#     ps_a_u = download_file_from_s3(part_of_speech_audio_url, word)
#     o_a_u = download_file_from_s3(origin_audio_url, word)
#     u_a_u = download_file_from_s3(usage_audio_url, word)
#
#     word.usage = data["usage"]
#     word.meaning = data["meaning"]
#     word.part_of_speech = data["part_of_speech"]
#     word.origin = data["origin"]
#
#     WordAudios.objects.update_or_create(
#         word=word,
#         defaults={
#             "pronunciation_audio_url": p_a_u,
#             "meaning_audio_url": m_a_u,
#             "part_of_speech_audio_url": ps_a_u,
#             "origin_audio_url": o_a_u,
#             "usage_audio_url": u_a_u,
#         }
#     )
#     word.voice_status = "GENERATED"
#     word.save()
#     return True, "Audio files generated."
#
#
# class WordsAudio(APIView):
#
#     def post(self, request):
#         if not request.user.is_admin:
#             return CustomResponse().errorResponse(
#                 data={},
#                 description="Unauthorized"
#             )
#         word_id = request.data.get("word_id")
#         word = Words.objects.filter(id=word_id, voice_status='PENDING').first()
#         if not word:
#             return CustomResponse().errorResponse(
#                 data={},
#                 description="No Word found with provided ID or already generated"
#             )
#         resp = getWordAudio(word)
#         if resp[0]:
#             return CustomResponse().successResponse(
#                 data={},
#                 description="Audio files generated."
#             )
#         else:
#             return CustomResponse().errorResponse(
#                 data={},
#                 description=resp[1]
#             )




class WordsCrud(APIView):
    permission_classes = [IsAuthenticated]
    required_permissions = {"GET": "vocabbee.word.view", "POST": "vocabbee.word.create", "PUT": "vocabbee.word.update",
                            "DELETE": "vocabbee.word.delete"}

    def post(self, request):



        grade_id = request.data.get("grade_id")
        word = request.data.get("word")

        if not grade_id:
            return CustomResponse().errorResponse(
                data={},
                description="Grade is required"
            )

        if not word or not word.strip():
            return CustomResponse().errorResponse(
                data={},
                description="Word is required"
            )

        grade = Grades.objects.filter(
            id=grade_id,
            is_active=True
        ).first()

        if not grade:
            return CustomResponse().errorResponse(
                data={},
                description="Invalid grade"
            )

        word = word.strip()

        if Words.objects.filter(
            grade=grade,
            word__iexact=word
        ).exists():
            return CustomResponse().errorResponse(
                data={},
                description="Word already exists for this grade"
            )

        word_obj = Words.objects.create(
            grade=grade,
            word=word,
            subject=request.data.get("subject", "English"),
            concept=request.data.get("concept"),
            hint=request.data.get("hint"),
            meaning=request.data.get("meaning"),
            difficulty=request.data.get("difficulty", 1),
            part_of_speech=request.data.get("part_of_speech"),
            origin=request.data.get("origin"),
            usage=request.data.get("usage"),

            # New fields
            root_word=request.data.get("root_word"),
            phonetic_script=request.data.get("phonetic_script"),
            syllabified_stressed_transcript=request.data.get(
                "syllabified_stressed_transcript"
            ),
            origin_word=request.data.get("origin_word"),
            origin_word_meaning=request.data.get("origin_word_meaning"),
            antonym=request.data.get("antonym"),
            synonym=request.data.get("synonym"),
            points=request.data.get("points", 0),
            word_status=request.data.get("word_status"),
            domain=request.data.get("domain"),
        )

        # resp = getWordAudio(word_obj)

        return CustomResponse().successResponse(
            data={
                "word_id": str(word_obj.id),
                # "audio_generated": resp[0],
                # "audio_description": resp[1],
            },
            description="Word created successfully"
        )

    def get(self, request):



        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 20))

        search = request.GET.get("search")
        grade_id = request.GET.get("grade_id")
        difficulty = request.GET.get("difficulty")

        words = Words.objects.filter(
            is_active=True,
            voice_status="GENERATED"
        ).select_related(
            "grade",
            "audio"
        )

        if grade_id:
            words = words.filter(
                grade_id=grade_id
            )

        if difficulty:
            words = words.filter(
                difficulty=difficulty
            )

        if search:
            words = words.filter(
                Q(word__icontains=search)
            )

        total_count = words.count()

        start = (page - 1) * page_size
        end = start + page_size

        words = words.order_by(
            "is_valid",
            "word"
        )[start:end]

        response = []

        for word in words:

            word_details = {
                "word_id": str(word.id),
                "word": word.word,
                "subject": word.subject,
                "concept": word.concept,
                "hint": word.hint,
                "difficulty": word.difficulty,
                "meaning": word.meaning,
                "part_of_speech": word.part_of_speech,
                "origin": word.origin,
                "usage": word.usage,

                # New fields
                "root_word": word.root_word,
                "phonetic_script": word.phonetic_script,
                "syllabified_stressed_transcript": (
                    word.syllabified_stressed_transcript
                ),
                "origin_word": word.origin_word,
                "origin_word_meaning": word.origin_word_meaning,
                "antonym": word.antonym,
                "synonym": word.synonym,
                "points": word.points,
                "word_status": word.word_status,
                "domain": word.domain,

                # Existing fields
                "voice_status": word.voice_status,
                "is_valid": word.is_valid,
                "validation_reason": word.validation_reason,
                "validation_source": word.validation_source,
                "validated_at": word.validated_at,

                "grade": {
                    "id": str(word.grade.id),
                    "name": word.grade.name
                }
            }

            if hasattr(word, "audio"):
                word_details["pronunciation_audio_url"] = (
                    word.audio.pronunciation_audio_url
                )
                word_details["meaning_audio_url"] = (
                    word.audio.meaning_audio_url
                )
                word_details["part_of_speech_audio_url"] = (
                    word.audio.part_of_speech_audio_url
                )
                word_details["origin_audio_url"] = (
                    word.audio.origin_audio_url
                )
                word_details["usage_audio_url"] = (
                    word.audio.usage_audio_url
                )
                word_details["syllabified_stressed_transcript_audio_url"] = (
                    word.audio.syllabified_stressed_transcript_audio_url
                )
                word_details["phonetic_script_audio_url"] = (
                    word.audio.phonetic_script_audio_url
                )

            response.append(word_details)

        return CustomResponse().successResponse(
            data=response,
            total=total_count,
            description="Words fetched successfully"
        )

    def put(self, request):



        word_id = request.data.get("word_id")

        word_obj = Words.objects.filter(
            id=word_id,
            is_active=True
        ).first()

        if not word_obj:
            return CustomResponse().errorResponse(
                data={},
                description="Invalid word"
            )

        grade_id = request.data.get(
            "grade_id",
            word_obj.grade_id
        )

        grade = Grades.objects.filter(
            id=grade_id,
            is_active=True
        ).first()

        if not grade:
            return CustomResponse().errorResponse(
                data={},
                description="Invalid grade"
            )

        new_word = request.data.get(
            "word",
            word_obj.word
        )

        if not new_word or not new_word.strip():
            return CustomResponse().errorResponse(
                data={},
                description="Word is required"
            )

        new_word = new_word.strip()

        duplicate = Words.objects.filter(
            grade=grade,
            word__iexact=new_word,
            is_active=True
        ).exclude(
            id=word_obj.id
        ).exists()

        if duplicate:
            return CustomResponse().errorResponse(
                data={},
                description="Word already exists for this grade"
            )

        word_obj.word = new_word
        word_obj.grade = grade

        # Existing fields
        word_obj.difficulty = request.data.get(
            "difficulty",
            word_obj.difficulty
        )

        word_obj.meaning = request.data.get(
            "meaning",
            word_obj.meaning
        )

        word_obj.part_of_speech = request.data.get(
            "part_of_speech",
            word_obj.part_of_speech
        )

        word_obj.subject = request.data.get(
            "subject",
            word_obj.subject
        )

        word_obj.origin = request.data.get(
            "origin",
            word_obj.origin
        )

        word_obj.usage = request.data.get(
            "usage",
            word_obj.usage
        )

        word_obj.hint = request.data.get(
            "hint",
            word_obj.hint
        )

        word_obj.concept = request.data.get(
            "concept",
            word_obj.concept
        )

        # New fields
        word_obj.root_word = request.data.get(
            "root_word",
            word_obj.root_word
        )

        word_obj.phonetic_script = request.data.get(
            "phonetic_script",
            word_obj.phonetic_script
        )

        word_obj.syllabified_stressed_transcript = request.data.get(
            "syllabified_stressed_transcript",
            word_obj.syllabified_stressed_transcript
        )

        word_obj.origin_word = request.data.get(
            "origin_word",
            word_obj.origin_word
        )

        word_obj.origin_word_meaning = request.data.get(
            "origin_word_meaning",
            word_obj.origin_word_meaning
        )

        word_obj.antonym = request.data.get(
            "antonym",
            word_obj.antonym
        )

        word_obj.synonym = request.data.get(
            "synonym",
            word_obj.synonym
        )

        word_obj.points = request.data.get(
            "points",
            word_obj.points
        )

        word_obj.word_status = request.data.get(
            "word_status",
            word_obj.word_status
        )

        word_obj.domain = request.data.get(
            "domain",
            word_obj.domain
        )

        # Manual validation
        if "is_valid" in request.data:

            word_obj.is_valid = request.data.get("is_valid")

            word_obj.validation_reason = request.data.get(
                "validation_reason",
                word_obj.validation_reason
            )

            word_obj.validation_source = Words.ValidationSource.MANUAL
            word_obj.validated_at = timezone.now()
            word_obj.validated_by = request.user

        word_obj.updated_by = str(request.user)

        word_obj.save()

        return CustomResponse().successResponse(
            data={
                "word_id": str(word_obj.id)
            },
            description="Word updated successfully"
        )

    def delete(self, request):



        word_id = request.data.get("word_id")

        word_obj = Words.objects.filter(
            id=word_id,
            is_active=True,
            is_valid=False
        ).first()

        if not word_obj:
            return CustomResponse().errorResponse(
                data={},
                description="Invalid word"
            )

        word_obj.is_active = False
        word_obj.updated_by = str(request.user)
        word_obj.save()

        return CustomResponse().successResponse(
            data={},
            description="Word deleted successfully"
        )


# class UploadWords(APIView):
#
#     permission_classes = [AllowAny]
#     parser_classes = [MultiPartParser, FormParser]
#
#     def post(self, request):
#
#         # if not request.user.is_admin:
#         #     return CustomResponse().errorResponse(
#         #         data={},
#         #         description="Unauthorized"
#         #     )
#
#         file = request.FILES.get("file")
#
#         if not file:
#             return CustomResponse().errorResponse(
#                 data={},
#                 description="File is required"
#             )
#
#         try:
#
#             df = pd.read_excel(file)
#             required_columns = [
#                 "Grade",
#                 "Word",
#                 "Difficulty"
#             ]
#             missing_columns = [
#                 column
#                 for column in required_columns
#                 if column not in df.columns
#             ]
#
#             if missing_columns:
#
#                 return CustomResponse().errorResponse(
#                     data={},
#                     description=f"Missing columns: {', '.join(missing_columns)}"
#                 )
#
#             grades_map = {
#                 grade.name.strip().lower(): grade
#                 for grade in Grades.objects.filter(
#                     is_active=True
#                 )
#             }
#
#             existing_words = set(
#                 Words.objects.filter(
#                     is_active=True
#                 ).values_list(
#                     "word",
#                     flat=True
#                 )
#             )
#
#             words_to_create = []
#
#             skipped_count = 0
#
#             for _, row in df.iterrows():
#
#                 grade_name = str(
#                     row["Grade"]
#                 ).strip()
#
#                 word = str(
#                     row["Word"]
#                 ).strip()
#
#                 if not word:
#                     continue
#
#                 grade = grades_map.get(
#                     grade_name.lower()
#                 )
#
#                 if not grade:
#                     skipped_count += 1
#                     continue
#
#                 if word in existing_words:
#                     skipped_count += 1
#                     continue
#
#                 words_to_create.append(
#                     Words(
#                         grade=grade,
#                         word=word,
#                         difficulty=row.get("Difficulty",1),
#                         subject=row.get('Subject','English'),
#                         concept=row.get('Concept',None),
#                         hint=row.get('Hint',None),
#                         meaning=row.get("Meaning"),
#                         part_of_speech=row.get(
#                             "Part Of Speech"
#                         ),
#                         origin=row.get(
#                             "Origin"
#                         ),
#                         usage=row.get(
#                             "Usage"
#                         )
#                     )
#                 )
#
#                 existing_words.add(word)
#
#             Words.objects.bulk_create(
#                 words_to_create,
#                 batch_size=1000
#             )
#
#             return CustomResponse().successResponse(
#                 data={
#                     "created_count": len(words_to_create),
#                     "skipped_count": skipped_count
#                 },
#                 description="Words uploaded successfully"
#             )
#
#         except Exception as e:
#             return CustomResponse().errorResponse(
#                 data={},
#                 description=str(e)
#             )





class UploadWords(APIView):

    permission_classes = [IsAuthenticated]

    parser_classes = [
        MultiPartParser,
        FormParser
    ]
    required_permission = "vocabbee.word.import"

    def post(self, request):

        file = request.FILES.get("file")

        if not file:
            return CustomResponse().errorResponse(
                data={},
                description="File is required."
            )

        try:
            df = pd.read_excel(file)
            df.columns = df.columns.str.strip()

            # Required Excel columns
            required_columns = [
                "Grade",
                "Word",
                "Difficulty Level"
            ]

            missing_columns = [
                column for column in required_columns
                if column not in df.columns
            ]

            if missing_columns:
                return CustomResponse().errorResponse(
                    data={
                        "missing_columns": missing_columns
                    },
                    description=(
                        f"Missing required columns: "
                        f"{', '.join(missing_columns)}"
                    )
                )

            # Helper to get Excel values
            def get_value(row, *columns, default=None):

                for column in columns:

                    if column not in row.index:
                        continue

                    value = row.get(column)

                    if pd.isna(value):
                        continue

                    if isinstance(value, str):
                        value = value.strip()

                    if value != "":
                        return value

                return default

            # Validate required values before processing
            required_errors = []

            for index, row in df.iterrows():

                excel_row = index + 2

                missing_fields = []

                for field in required_columns:

                    value = get_value(row, field)

                    if value is None:
                        missing_fields.append(field)

                if missing_fields:
                    required_errors.append({
                        "row": excel_row,
                        "missing_fields": missing_fields
                    })

            if required_errors:
                return CustomResponse().errorResponse(
                    data={
                        "required_errors": required_errors
                    },
                    description=(
                        "Required fields cannot be empty or NULL. "
                        "Please correct the Excel file."
                    )
                )

            # Active grades
            grades_map = {
                grade.name.strip().lower(): grade
                for grade in Grades.objects.filter(is_active=True)
            }

            # Existing words
            existing_words = {
                (word.strip().lower(), str(grade_id))
                for word, grade_id in Words.objects.filter(
                    is_active=True
                ).values_list("word", "grade_id")
                if word
            }

            seen_in_file = set()
            words_to_create = []

            created_count = 0
            duplicate_count = 0
            invalid_grade_count = 0
            missing_word_count = 0

            duplicate_words = []
            invalid_grades = []
            missing_words = []
            null_fields = []

            # Excel to model field mapping
            field_mapping = {
                "meaning": ["Definition/ meaning", "Meaning"],
                "root_word": ["Root word"],
                "phonetic_script": ["Phonetic script"],
                "syllabified_stressed_transcript": [
                    "Syallabified Stressed Transcript",
                    "Syllabified Stressed Transcript"
                ],
                "concept": ["Concept name", "Concept"],
                "origin": ["Origin"],
                "origin_word": ["Origin Word (Exact Word)"],
                "origin_word_meaning": ["Origin Word Meaning"],
                "usage": ["Usage"],
                "hint": ["Hint"],
                "antonym": ["Antonym"],
                "synonym": ["Synonym"],
                "part_of_speech": ["Parts Of Speech", "Part Of Speech"],
                "word_status": ["Status"],
                "domain": ["Domain"],
            }

            for index, row in df.iterrows():

                excel_row = index + 2

                grade_value = get_value(row, "Grade")
                word_value = get_value(row, "Word")

                grade_name = str(grade_value).strip()
                word = str(word_value).strip().lower()

                grade = grades_map.get(grade_name.lower())

                if not grade:

                    invalid_grade_count += 1

                    invalid_grades.append({
                        "row": excel_row,
                        "grade": grade_name
                    })

                    continue

                duplicate_key = (word, str(grade.id))

                # Duplicate in uploaded Excel
                if duplicate_key in seen_in_file:

                    duplicate_count += 1

                    duplicate_words.append({
                        "row": excel_row,
                        "word": word,
                        "grade": grade.name,
                        "reason": "Duplicate in uploaded file"
                    })

                    continue

                seen_in_file.add(duplicate_key)

                # Duplicate in database
                if duplicate_key in existing_words:

                    duplicate_count += 1

                    duplicate_words.append({
                        "row": excel_row,
                        "word": word,
                        "grade": grade.name,
                        "reason": "Already exists"
                    })

                    continue

                existing_words.add(duplicate_key)

                # Difficulty validation
                difficulty = get_value(
                    row,
                    "Difficulty Level"
                )

                try:
                    difficulty = int(float(difficulty))

                    if difficulty < 1 or difficulty > 5:
                        raise ValueError

                except (ValueError, TypeError):
                    return CustomResponse().errorResponse(
                        data={
                            "row": excel_row,
                            "difficulty": difficulty
                        },
                        description=(
                            "Difficulty Level must be between 1 and 5."
                        )
                    )

                # Points validation
                points = get_value(row, "Points", default=0)

                try:
                    points = int(float(points))

                    if points < 0:
                        raise ValueError

                except (ValueError, TypeError):
                    return CustomResponse().errorResponse(
                        data={
                            "row": excel_row,
                            "points": points
                        },
                        description=(
                            "Points must be a non-negative number."
                        )
                    )

                # Optional fields
                optional_values = {}

                empty_fields = []

                for model_field, excel_columns in field_mapping.items():

                    value = get_value(
                        row,
                        *excel_columns
                    )

                    optional_values[model_field] = value

                    if value is None:
                        empty_fields.append(model_field)

                # Subject
                subject = get_value(
                    row,
                    "subject",
                    "Subject",
                    default="English"
                )

                if subject is None:
                    subject = "English"

                # Record optional NULL fields
                if empty_fields:

                    null_fields.append({
                        "row": excel_row,
                        "word": word,
                        "fields": empty_fields
                    })

                # Create word object
                words_to_create.append(
                    Words(
                        grade=grade,
                        word=word,
                        difficulty=difficulty,
                        points=points,
                        subject=subject,
                        **optional_values
                    )
                )

                created_count += 1

            # Bulk create
            with transaction.atomic():

                if words_to_create:
                    Words.objects.bulk_create(
                        words_to_create,
                        batch_size=1000
                    )

            return CustomResponse().successResponse(
                data={
                    "summary": {
                        "total_rows": len(df),
                        "created_count": created_count,
                        "duplicate_count": duplicate_count,
                        "invalid_grade_count": invalid_grade_count,
                        "missing_word_count": missing_word_count
                    },
                    "duplicate_words": duplicate_words,
                    "invalid_grades": invalid_grades,
                    "missing_words": missing_words,
                    "null_fields": null_fields
                },
                description="Words uploaded successfully."
            )

        except IntegrityError:

            return CustomResponse().errorResponse(
                data={},
                description=(
                    "Upload failed because duplicate words already exist. "
                    "Please verify the Excel file and try again."
                )
            )

        except Exception as e:



            return CustomResponse().errorResponse(
                data={},
                description=str(e)
            )





class DashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]
    required_permission = "vocabbee.dashboard.view"

    def get(self, request):
        today = timezone.localdate()
        total_users = UserMaster.objects.count()
        total_words = Words.objects.count()
        audio_generated = WordAudios.objects.count()
        audio_pending = max(
            total_words - audio_generated,
            0
        )
        total_word_attempts = PracticeAttempts.objects.count()
        daily_active_users = PracticeAttempts.objects.filter(
            created_at__date=today
        ).values(
            "kid"
        ).distinct().count()
        return CustomResponse().successResponse(data={
                "total_users": total_users,
                "total_words": total_words,
                "audio_generated": audio_generated,
                "audio_pending": audio_pending,
                "total_word_attempts": total_word_attempts,
                "daily_active_users": daily_active_users
        })


class SubjectCrud(APIView):
    permission_classes = [IsAuthenticated]
    required_permissions = {"GET": "vocabbee.subject.view", "POST": "vocabbee.subject.create"}

    def post(self, request):
        name = request.data.get("name", "").strip()
        description = request.data.get("description")
        icon = request.data.get("icon")
        color_code = request.data.get("color_code", "#4F46E5")
        display_order = request.data.get("display_order", 0)

        if not name:
            return CustomResponse().errorResponse(
                description="Subject name is required."
            )

        if Subjects.objects.filter(
            name__iexact=name,
        ).exists():
            return CustomResponse().errorResponse(
                description="Subject already exists."
            )

        subject = Subjects.objects.create(
            name=name,
            description=description,
            icon=icon,
            color_code=color_code,
            display_order=display_order
        )

        return CustomResponse().successResponse(
            data={
                "id": subject.id
            },
            description="Subject created successfully."
        )

    def get(self, request):

        subjects = Subjects.objects.all().order_by(
            "display_order",
            "name"
        )

        data = []

        for subject in subjects:
            data.append({
                "id": subject.id,
                "name": subject.name,
                "description": subject.description,
                "icon": subject.icon,
                "color_code": subject.color_code,
                "display_order": subject.display_order,
                "is_active": subject.is_active
            })

        return CustomResponse().successResponse(data=data)

class SubjectDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]
    required_permission = "vocabbee.subject.delete"
    def delete(self, request, subject_id):
        subject = Subjects.objects.filter(
            id=subject_id
        ).first()
        if not subject:
            return CustomResponse().errorResponse(
                description="Subject not found."
            )
        if subject.words.exists():
            return CustomResponse().errorResponse(
                description="This subject cannot be deleted because it is associated with one or more words."
            )
        subject.delete()
        return CustomResponse().successResponse(
            data={},
            description="Subject deleted successfully."
        )


class TournamentCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    required_permissions = {"GET": "vocabbee.tournament.view", "POST": "vocabbee.tournament.create"}

    def post(self, request):
        data = request.data
        title = data.get("title")
        description = data.get("description")
        tournament_type = data.get("tournament_type")
        total_questions = data.get("total_questions")
        duration_minutes = data.get("duration_minutes")
        start_at = data.get("start_at")
        end_at = data.get("end_at")
        max_participants = data.get("max_participants")
        entry_fee = data.get("entry_fee", 0)
        prize_pool = data.get("prize_pool", 0)
        if not title:
            return CustomResponse().errorResponse(
                description="Tournament title is required."
            )
        if not tournament_type:
            return CustomResponse().errorResponse(
                description="Tournament type is required."
            )
        if not total_questions:
            return CustomResponse().errorResponse(
                description="Total questions is required."
            )
        if not duration_minutes:
            return CustomResponse().errorResponse(
                description="Duration is required."
            )
        if not start_at:
            return CustomResponse().errorResponse(
                description="Start date & time is required."
            )
        if not end_at:
            return CustomResponse().errorResponse(
                description="End date & time is required."
            )
        # if Tournaments.objects.filter(
        #     title__iexact=title.strip()
        # ).exists():
        #     return CustomResponse().errorResponse(
        #         description="Tournament with this title already exists."
        #     )

        subject = None
        # if subject_id:
        #
        #     subject = Subjects.objects.filter(
        #         id=subject_id
        #     ).first()
        #
        #     if not subject:
        #         return CustomResponse().errorResponse(
        #             description="Invalid subject."
        #         )
        tournament = Tournaments.objects.create(
            title=title.strip(),
            description=description,
            tournament_type=tournament_type,
            subject=subject,
            total_questions=total_questions,
            duration_minutes=duration_minutes,
            start_at=start_at,
            end_at=end_at,
            max_participants=max_participants,
            entry_fee=entry_fee,
            prize_pool=prize_pool,
            status="DRAFT"
        )
        return CustomResponse().successResponse(
            data={
                "id": str(tournament.id)
            },
            description="Tournament created successfully."
        )
    def get(self, request):

        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 20))

        status = request.GET.get("status")
        tournament_type = request.GET.get("tournament_type")
        subject_id = request.GET.get("subject_id")
        search = request.GET.get("search")

        tournaments = Tournaments.objects.annotate(
            participant_count=Count("participants", distinct=True),
            grade_count=Count("eligible_grades", distinct=True),
            question_count=Count("questions", distinct=True)
        ).order_by("-created_at")

        if status:
            tournaments = tournaments.filter(status=status)

        if tournament_type:
            tournaments = tournaments.filter(
                tournament_type=tournament_type
            )

        if subject_id:
            tournaments = tournaments.filter(
                subject_id=subject_id
            )

        if search:
            tournaments = tournaments.filter(
                title__icontains=search
            )

        paginator = Paginator(
            tournaments,
            page_size
        )

        page_obj = paginator.get_page(page)

        data = []

        for tournament in page_obj:

            data.append({
                "id": str(tournament.id),
                "title": tournament.title,
                "subject": tournament.subject.name if tournament.subject else "",
                "tournament_type": tournament.tournament_type,
                "status": tournament.status,
                "total_questions": tournament.total_questions,
                "assigned_questions": tournament.question_count,
                "eligible_grades": tournament.grade_count,
                "participants": tournament.participant_count,
                "start_at": tournament.start_at,
                "end_at": tournament.end_at,
                "prize_pool": tournament.prize_pool,
                "max_participants": tournament.max_participants,
                "duration": tournament.duration_minutes,
            })

        return CustomResponse().successResponse(
            data={
                "current_page": page,
                "page_size": page_size,
                "total_pages": paginator.num_pages,
                "total_records": paginator.count,
                "results": data
            }
        )

class TournamentDetailsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    required_permission = "vocabbee.tournament.view"

    def get(self, request, tournament_id):

        tournament = Tournaments.objects.filter(
            id=tournament_id
        ).first()

        if not tournament:
            return CustomResponse().errorResponse(
                description="Tournament not found."
            )

        grades = []

        tournament_grades = TournamentGrades.objects.filter(
            tournament=tournament
        ).select_related("grade")

        for item in tournament_grades:
            grades.append({
                "id": str(item.grade.id),
                "name": item.grade.name
            })

        words = []

        tournament_questions = TournamentQuestions.objects.filter(
            tournament=tournament
        ).select_related("word").order_by("display_order")

        for item in tournament_questions:
            words.append({
                "tournament_question_id": str(item.id),
                "word_id": str(item.word.id),
                "display_order": item.display_order,
                "word": item.word.word
            })

        participant_count = TournamentParticipants.objects.filter(
            tournament=tournament
        ).count()

        return CustomResponse().successResponse(
            data={
                "id": str(tournament.id),
                "title": tournament.title,
                "description": tournament.description,
                "tournament_type": tournament.tournament_type,
                "status": tournament.status,
                "total_questions": tournament.total_questions,
                "duration_minutes": tournament.duration_minutes,
                "start_at": tournament.start_at,
                "end_at": tournament.end_at,
                "max_participants": tournament.max_participants,
                "entry_fee": tournament.entry_fee,
                "prize_pool": tournament.prize_pool,

                "total_grades": len(grades),
                "total_words": len(words),
                "total_participants": participant_count,

                "grades": grades,
                "words": words
            },
            description="Tournament details fetched successfully."
        )


class TournamentAssignGradesAPIView(APIView):
    permission_classes = [IsAuthenticated]
    required_permission = "vocabbee.tournament.update"

    def post(self, request, tournament_id):
        data = request.data
        grade_ids = data.get("grades", [])
        tournament = Tournaments.objects.filter(
            id=tournament_id
        ).first()
        if not tournament:
            return CustomResponse().errorResponse(
                description="Tournament not found."
            )
        if tournament.status != "DRAFT":
            return CustomResponse().errorResponse(
                description="Grades can only be updated while the tournament is in Draft status."
            )
        if not isinstance(grade_ids, list):
            return CustomResponse().errorResponse(
                description="Grades should be a list."
            )
        grades = Grades.objects.filter(
            id__in=grade_ids,
            is_active=True
        )
        if grades.count() != len(set(grade_ids)):
            return CustomResponse().errorResponse(
                description="One or more selected grades are invalid."
            )
        TournamentGrades.objects.filter(
            tournament=tournament
        ).delete()
        mappings = []
        for grade in grades:
            mappings.append(
                TournamentGrades(
                    tournament=tournament,
                    grade=grade
                )
            )
        TournamentGrades.objects.bulk_create(mappings)
        return CustomResponse().successResponse(
            data={
                "total_grades": len(mappings)
            },
            description="Grades assigned successfully."
        )


class TournamentAvailableWordsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    required_permission = "vocabbee.tournament.view"

    def post(self, request):
        page = int(request.data.get("page", 1))
        page_size = int(request.data.get("page_size", 20))
        search = request.data.get("search")
        grade_ids = request.data.get("grade_ids")
        # difficulty_levels = request.data.getlist("difficulty_levels")
        words = Words.objects.filter(
            is_active=True,
            voice_status='GENERATED',
        ).select_related(
            "grade",
        ).order_by(
            "word"
        )
        if search:
            words = words.filter(
                word__icontains=search
            )
        if grade_ids:
            words = words.filter(
                grade_id__in=grade_ids
            )
        paginator = Paginator(words, page_size)
        page_obj = paginator.get_page(page)
        results = []
        for word in page_obj:
            results.append({
                "id": str(word.id),
                "word": word.word,
                "grade": {
                    "id": str(word.grade.id),
                    "name": word.grade.name
                } if word.grade else None,
            })
        return CustomResponse().successResponse(
            data={
                "current_page": page,
                "page_size": page_size,
                "total_pages": paginator.num_pages,
                "total_records": paginator.count,
                "results": results
            },
            description="Words fetched successfully."
        )

class TournamentAssignQuestionsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    required_permission = "vocabbee.tournament.update"

    def post(self, request, tournament_id):

        data = request.data
        words = data.get("words", [])
        tournament = Tournaments.objects.filter(
            id=tournament_id
        ).first()
        if not tournament:
            return CustomResponse().errorResponse(
                description="Tournament not found."
            )
        if tournament.status != "DRAFT":
            return CustomResponse().errorResponse(
                description="Questions can only be updated while the tournament is in Draft status."
            )
        if not isinstance(words, list):
            return CustomResponse().errorResponse(
                description="Words should be a list."
            )
        if len(words) == 0:
            return CustomResponse().errorResponse(
                description="Please select at least one word."
            )
        word_ids = [item.get("word_id") for item in words]
        db_words = Words.objects.filter(
            id__in=word_ids,
            is_active=True
        )
        if db_words.count() != len(set(word_ids)):
            return CustomResponse().errorResponse(
                description="One or more selected words are invalid."
            )
        if len(words) != tournament.total_questions:
            return CustomResponse().errorResponse(
                description=f"Please assign exactly {tournament.total_questions} questions."
            )
        word_map = {}
        for word in db_words:
            word_map[str(word.id)] = word
        TournamentQuestions.objects.filter(
            tournament=tournament
        ).delete()
        mappings = []
        for item in words:
            word = word_map.get(item.get("word_id"))
            if not word:
                continue
            mappings.append(
                TournamentQuestions(
                    tournament=tournament,
                    word=word,
                    display_order=item.get("display_order")
                )
            )
        TournamentQuestions.objects.bulk_create(mappings)
        return CustomResponse().successResponse(
            data={
                "total_questions": len(mappings)
            },
            description="Questions assigned successfully."
        )

class TournamentPublishAPIView(APIView):
    permission_classes = [IsAuthenticated]
    required_permission = "vocabbee.tournament.publish"

    def post(self, request, tournament_id):

        tournament = Tournaments.objects.filter(
            id=tournament_id
        ).first()

        if not tournament:
            return CustomResponse().errorResponse(
                description="Tournament not found."
            )

        if tournament.status != "DRAFT":
            return CustomResponse().errorResponse(
                description="Only Draft tournaments can be published."
            )

        grades_count = TournamentGrades.objects.filter(
            tournament=tournament
        ).count()

        if grades_count == 0:
            return CustomResponse().errorResponse(
                description="Please assign at least one grade."
            )

        questions_count = TournamentQuestions.objects.filter(
            tournament=tournament
        ).count()

        if questions_count != tournament.total_questions:
            return CustomResponse().errorResponse(
                description=f"Please assign exactly {tournament.total_questions} questions."
            )

        if tournament.start_at >= tournament.end_at:
            return CustomResponse().errorResponse(
                description="End date & time should be greater than start date & time."
            )
        tournament.status = "UPCOMING"
        tournament.save()
        TournyReminders.tourney_active(tournament)
        return CustomResponse().successResponse(
            data={},
            description="Tournament published successfully."
        )

class TournamentCancelAPIView(APIView):
    permission_classes = [IsAuthenticated]
    required_permission = "vocabbee.tournament.cancel"

    def post(self, request, tournament_id):

        tournament = Tournaments.objects.filter(
            id=tournament_id
        ).first()
        if not tournament:
            return CustomResponse().errorResponse(
                description="Tournament not found."
            )
        if tournament.status == "CANCELLED":
            return CustomResponse().errorResponse(
                description="Tournament is already cancelled."
            )
        if tournament.status == "COMPLETED":
            return CustomResponse().errorResponse(
                description="Completed tournaments cannot be cancelled."
            )
        if tournament.status == "LIVE":
            return CustomResponse().errorResponse(
                description="Live tournaments cannot be cancelled."
            )
        tournament.status = "CANCELLED"
        tournament.save()
        return CustomResponse().successResponse(
            data={},
            description="Tournament cancelled successfully."
        )


class TournyReminders:
    @classmethod
    def tourney_active(cls, tournament):
        eligible_grade_ids = TournamentGrades.objects.filter(
            tournament=tournament
        ).values_list(
            "grade_id",
            flat=True
        )
        user_ids = UserMaster.objects.filter(
            kids__grade_id__in=eligible_grade_ids,
        ).distinct().values_list(
            "id",
            flat=True
        )
        tokens = Devices.objects.filter(
            user_id__in=user_ids,
            is_active=True
        ).exclude(
            fcm_token=""
        ).values_list(
            "fcm_token",
            flat=True
        )
        tokens = set(tokens)
        # pushinfo = send_bulk_push_notification(list(tokens),
        #                                       "🏆 New Tournament Published",
        #                                       f"{tournament.title} is now open for registration.",
        #                                       {
        #                                           "tournament_id": tournament.id
        #                                       },
        #                                        "TOURNEY_PUBLISH",
        #                                        )
        # print(pushinfo)

