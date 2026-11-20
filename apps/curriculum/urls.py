from django.urls import path

from apps.curriculum.views.curriculum import CurriculumListAPIView, CurriculumCategoryListAPIView, \
    CurriculumSubjectListAPIView, CurriculumLessonListAPIView, CurriculumLessonDetailAPIView

urlpatterns = [

    path("curriculum",CurriculumListAPIView.as_view()),

    path("curriculum/<uuid:curriculum_id>/categories",CurriculumCategoryListAPIView.as_view()),

    path("curriculum/categories/<uuid:category_id>/subjects", CurriculumSubjectListAPIView.as_view()),

    path("curriculum/subjects/<uuid:subject_id>/lessons",CurriculumLessonListAPIView.as_view()),

    path("curriculum/lessons/<uuid:lesson_id>",CurriculumLessonDetailAPIView.as_view()),

]