from django.contrib import admin

from .models import StudyDocument


@admin.register(StudyDocument)
class StudyDocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'version', 'uploaded_by', 'updated_at']
    list_filter = ['category']
    search_fields = ['title', 'description', 'version']
    readonly_fields = ['uploaded_by', 'uploaded_at', 'updated_at']
