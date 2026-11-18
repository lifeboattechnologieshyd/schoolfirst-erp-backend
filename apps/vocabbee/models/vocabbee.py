# import uuid
#
# from django.core.validators import MinValueValidator, MaxValueValidator
# from django.db import models
#
# from apps.core.models import UserMaster
# from shared.mixins import AuditModel
#
#
# class Grades(AuditModel):
#     id = models.UUIDField(
#         primary_key=True,
#         default=uuid.uuid4,
#         editable=False
#     )
#     name = models.CharField(
#         max_length=50
#     )
#     sort_order = models.IntegerField(
#         default=1
#     )
#     is_active = models.BooleanField(
#         default=True
#     )
#     class Meta:
#         db_table = "grades"
#
#
# class Subjects(AuditModel):
#     id = models.UUIDField(
#         primary_key=True,
#         default=uuid.uuid4,
#         editable=False
#     )
#
#     name = models.CharField(
#         max_length=100,
#         unique=True
#     )
#
#     description = models.TextField(
#         null=True,
#         blank=True
#     )
#
#     icon = models.URLField(
#         null=True,
#         blank=True
#     )
#
#     color_code = models.CharField(
#         max_length=10,
#         default="#4F46E5"
#     )
#
#     display_order = models.IntegerField(
#         default=0
#     )
#
#     is_active = models.BooleanField(
#         default=True
#     )
#
#     class Meta:
#         db_table = "subjects"
#         ordering = ["display_order", "name"]
#
#     def __str__(self):
#         return self.name
#
# class Topics(AuditModel):
#     id = models.UUIDField(
#         primary_key=True,
#         default=uuid.uuid4,
#         editable=False
#     )
#
#     subject = models.ForeignKey(
#         Subjects,
#         on_delete=models.CASCADE,
#         related_name="topics"
#     )
#
#     name = models.CharField(
#         max_length=100
#     )
#
#     description = models.TextField(
#         null=True,
#         blank=True
#     )
#
#     display_order = models.IntegerField(
#         default=0
#     )
#
#     is_active = models.BooleanField(
#         default=True
#     )
#
#     class Meta:
#         db_table = "topics"
#         unique_together = ("subject", "name")
#
#
# class Kids(AuditModel):
#
#     id = models.UUIDField(
#         primary_key=True,
#         default=uuid.uuid4,
#         editable=False
#     )
#
#     parent = models.ForeignKey(
#         UserMaster,
#         on_delete=models.CASCADE,
#         related_name="kids"
#     )
#
#     grade = models.ForeignKey(
#         Grades,
#         on_delete=models.PROTECT,
#         related_name="kids"
#     )
#
#     name = models.CharField(
#         max_length=100
#     )
#     date_of_birth = models.DateField(null=True, blank=True)
#
#     profile_image = models.CharField(
#         max_length=500,
#         blank=True,
#         null=True
#     )
#
#     is_active = models.BooleanField(
#         default=True
#     )
#
#     class Meta:
#         db_table = "kids"
#
# class Words(AuditModel):
#     class ValidationSource(models.TextChoices):
#         AI = "AI", "AI"
#         MANUAL = "MANUAL", "Manual"
#     VOICE_STATUS = (
#         ("GENERATED", "GENERATED"),
#         ("PENDING", "PENDING"),
#     )
#     id = models.UUIDField(
#         primary_key=True,
#         default=uuid.uuid4,
#         editable=False
#     )
#
#     grade = models.ForeignKey(
#         Grades,
#         on_delete=models.PROTECT,
#         related_name="words"
#     )
#
#     word = models.CharField(
#         max_length=255
#     )
#     subject = models.CharField(
#         max_length=255, default="English"
#     )
#     category = models.ForeignKey(
#         Subjects,
#         on_delete=models.PROTECT,
#         null=True,
#         related_name="words"
#     )
#     concept = models.CharField(max_length=255, null=True)
#     hint = models.CharField(max_length=500, null=True)
#     difficulty = models.PositiveSmallIntegerField(
#         default=1,
#         validators=[
#             MinValueValidator(1),
#             MaxValueValidator(5)
#         ]
#     )
#     meaning = models.TextField(
#         blank=True,
#         null=True
#     )
#     part_of_speech = models.CharField(
#         max_length=100,
#         blank=True,
#         null=True
#     )
#     origin = models.CharField(
#         max_length=255,
#         blank=True,
#         null=True
#     )
#     usage = models.TextField(
#         blank=True,
#         null=True
#     )
#     is_active = models.BooleanField(
#         default=True
#     )
#     voice_status = models.CharField(
#         max_length=20,
#         choices=VOICE_STATUS,
#         default="PENDING",
#         db_index=True
#     )
#     is_valid = models.BooleanField(
#         null=True,
#         blank=True,
#         db_index=True,
#     )
#
#     validation_source = models.CharField(
#         max_length=10,
#         choices=ValidationSource.choices,
#         null=True,
#         blank=True,
#         db_index=True,
#     )
#
#     validated_by = models.ForeignKey(
#         UserMaster,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name="validated_words",
#         help_text="User who manually validated the word."
#     )
#
#     validated_at = models.DateTimeField(
#         null=True,
#         blank=True,
#     )
#
#     validation_reason = models.TextField(
#         null=True,
#         blank=True,
#     )
#     root_word = models.CharField(
#         max_length=50,
#         null=True,
#         blank=True
#     )
#
#     phonetic_script = models.CharField(
#         max_length=50,
#         null=True,
#         blank=True,
#         help_text="Phonetic transcription (IPA)."
#     )
#
#     syllabified_stressed_transcript = models.CharField(
#         max_length=50,
#         null=True,
#         blank=True
#     )
#
#     origin_word = models.CharField(
#         max_length=50,
#         null=True,
#         blank=True
#     )
#
#     origin_word_meaning = models.TextField(
#         null=True,
#         blank=True
#     )
#
#     antonym = models.TextField(
#         null=True,
#         blank=True
#     )
#
#     synonym = models.TextField(
#         null=True,
#         blank=True
#     )
#
#     points = models.PositiveIntegerField(
#         default=0
#     )
#
#     word_status = models.CharField(
#         max_length=50,
#         null=True,
#         blank=True
#     )
#
#     domain = models.CharField(
#         max_length=50,
#         null=True,
#         blank=True
#     )
#
#
#     class Meta:
#         db_table = "words"
#         constraints = [
#             models.UniqueConstraint(
#                 fields=["grade", "word"],
#                 name="unique_grade_word",
#             )
#         ]
#         indexes = [
#             models.Index(
#                 fields=["grade"]
#             ),
#             models.Index(
#                 fields=["difficulty"]
#             ),
#             models.Index(
#                 fields=["is_active"]
#             ),
#             models.Index(
#                 fields=["grade", "difficulty"]
#             ),
#             models.Index(
#                 fields=["grade", "is_active"]
#             ),
#             models.Index(
#                 fields=["word"]
#             )
#         ]
#
# class WordAudios(AuditModel):
#
#     id = models.UUIDField(
#         primary_key=True,
#         default=uuid.uuid4,
#         editable=False
#     )
#
#     word = models.OneToOneField(
#         Words,
#         on_delete=models.CASCADE,
#         related_name="audio"
#     )
#
#     pronunciation_audio_url = models.CharField(
#         max_length=500,
#         null=True,
#         blank=True
#     )
#
#     meaning_audio_url = models.CharField(
#         max_length=500,
#         null=True,
#         blank=True
#     )
#
#     part_of_speech_audio_url = models.CharField(
#         max_length=500,
#         null=True,
#         blank=True
#     )
#
#     origin_audio_url = models.CharField(
#         max_length=500,
#         null=True,
#         blank=True
#     )
#
#     usage_audio_url = models.CharField(
#         max_length=500,
#         null=True,
#         blank=True
#     )
#     phonetic_script_audio_url = models.CharField(
#         max_length=500,
#         null=True,
#         blank=True
#     )
#     syllabified_stressed_transcript_audio_url = models.CharField(
#         max_length=500,
#         null=True,
#         blank=True
#
#     )
#     class Meta:
#         db_table = "word_audios"
#
#
# class DailyChallengeWords(AuditModel):
#     id = models.UUIDField(
#         primary_key=True,
#         default=uuid.uuid4,
#         editable=False
#     )
#     challenge_date = models.DateField()
#     grade = models.ForeignKey(
#         Grades,
#         on_delete=models.PROTECT
#     )
#     word = models.ForeignKey(
#         Words,
#         on_delete=models.PROTECT
#     )
#
#     order = models.IntegerField(
#         default=1
#     )
#     is_active = models.BooleanField(
#         default=True
#     )
#     class Meta:
#         db_table = "daily_challenge_words"
#         unique_together = (
#             "challenge_date",
#             "grade",
#             "word"
#         )
#
# class DailyChallengeAttempts(AuditModel):
#     STATUS = (
#         ("IN_PROGRESS", "IN_PROGRESS"),
#         ("COMPLETED", "COMPLETED"),
#     )
#     id = models.UUIDField(
#         primary_key=True,
#         default=uuid.uuid4,
#         editable=False
#     )
#     kid = models.ForeignKey(
#         Kids,
#         on_delete=models.CASCADE,
#         related_name="daily_challenge_attempts"
#     )
#     challenge_date = models.DateField()
#     grade = models.ForeignKey(
#         Grades,
#         on_delete=models.PROTECT
#     )
#     total_words = models.IntegerField(
#         default=10
#     )
#     attempted_words = models.IntegerField(
#         default=0
#     )
#     correct_words = models.IntegerField(
#         default=0
#     )
#     status = models.CharField(
#         max_length=20,
#         choices=STATUS,
#         default="IN_PROGRESS"
#     )
#     completed_at = models.DateTimeField(
#         null=True,
#         blank=True
#     )
#
#     class Meta:
#         db_table = "daily_challenge_attempts"
#         unique_together = (
#             "kid",
#             "challenge_date"
#         )
#
# class DailyChallengeAttemptAnswers(AuditModel):
#     id = models.UUIDField(
#         primary_key=True,
#         default=uuid.uuid4,
#         editable=False
#     )
#     challenge_attempt = models.ForeignKey(
#         DailyChallengeAttempts,
#         on_delete=models.CASCADE,
#         related_name="word_attempts"
#     )
#     word = models.ForeignKey(
#         Words,
#         on_delete=models.PROTECT
#     )
#     typed_answer = models.CharField(
#         max_length=255,
#         null=True,
#         blank=True
#     )
#     is_correct = models.BooleanField()
#     attempted_at = models.DateTimeField(
#         auto_now_add=True
#     )
#     class Meta:
#         db_table = "daily_challenge_attempt_answers"
#         unique_together = (
#             "challenge_attempt",
#             "word"
#         )
#
# class KidWordProgress(AuditModel):
#
#     id = models.UUIDField(
#         primary_key=True,
#         default=uuid.uuid4,
#         editable=False
#     )
#
#     kid = models.ForeignKey(
#         Kids,
#         on_delete=models.CASCADE,
#         related_name="word_progress"
#     )
#
#     word = models.ForeignKey(
#         Words,
#         on_delete=models.CASCADE,
#         related_name="kid_progress"
#     )
#
#     times_seen = models.PositiveIntegerField(
#         default=0
#     )
#
#     times_correct = models.PositiveIntegerField(
#         default=0
#     )
#
#     last_attempted_at = models.DateTimeField(
#         null=True,
#         blank=True
#     )
#
#     class Meta:
#         db_table = "kid_word_progress"
#
#         unique_together = (
#             "kid",
#             "word"
#         )
#
#         indexes = [
#             models.Index(
#                 fields=["kid"]
#             ),
#             models.Index(
#                 fields=["word"]
#             ),
#             models.Index(
#                 fields=["kid", "word"]
#             )
#         ]
#
#
# class PracticeAttempts(AuditModel):
#
#     id = models.UUIDField(
#         primary_key=True,
#         default=uuid.uuid4,
#         editable=False
#     )
#
#     kid = models.ForeignKey(
#         Kids,
#         on_delete=models.CASCADE,
#         related_name="practice_attempts"
#     )
#     total_questions = models.PositiveIntegerField(
#         default=0
#     )
#     skipped_answers = models.PositiveIntegerField(
#         default=0
#     )
#     wrong_answers = models.PositiveIntegerField(
#         default=0
#     )
#     correct_answers = models.PositiveIntegerField(
#         default=0
#     )
#     score = models.PositiveIntegerField(
#         default=0
#     )
#     started_at = models.DateTimeField()
#     completed_at = models.DateTimeField(
#         null=True,
#         blank=True
#     )
#     class Meta:
#         db_table = "practice_attempts"
#
#
# class PracticeAttemptAnswers(AuditModel):
#
#     id = models.UUIDField(
#         primary_key=True,
#         default=uuid.uuid4,
#         editable=False
#     )
#
#     attempt = models.ForeignKey(
#         PracticeAttempts,
#         on_delete=models.CASCADE,
#         related_name="answers"
#     )
#
#     word = models.ForeignKey(
#         Words,
#         on_delete=models.PROTECT
#     )
#
#     typed_answer = models.CharField(
#         max_length=255,
#         null=True,
#         blank=True
#     )
#
#     is_correct = models.BooleanField(
#         default=False
#     )
#
#     is_skipped = models.BooleanField(
#         default=False
#     )
#
#     time_taken_seconds = models.PositiveIntegerField(
#         default=0
#     )
#
#     class Meta:
#         db_table = "practice_attempt_answers"
#
#
#
# class Devices(AuditModel):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     user = models.ForeignKey(
#         UserMaster,
#         on_delete=models.CASCADE,
#         related_name="sessions",
#         null=True,
#         blank=True
#     )
#     device_id = models.CharField(
#         max_length=200,
#     )
#     platform = models.CharField(
#         max_length=20,
#         blank=True,
#         null=True
#     )
#     app_version = models.CharField(
#         max_length=20,
#         blank=True,
#         null=True
#     )
#     fcm_token = models.CharField(
#         max_length=500,
#         blank=True,
#         null=True
#     )
#     is_active = models.BooleanField(default=True)
#     last_login = models.DateTimeField(
#         blank=True,
#         null=True
#     )
#     class Meta:
#         db_table = "devices"