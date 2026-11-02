from django.contrib import admin

from .models import DerivedScore, FormSubmission


class DerivedScoreInline(admin.TabularInline):
    model = DerivedScore
    extra = 0
    can_delete = False
    readonly_fields = ('variable', 'number_value', 'text_value', 'rule_version')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(FormSubmission)
class FormSubmissionAdmin(admin.ModelAdmin):
    list_display = ('study_id', 'xml_form_id', 'facility', 'visit_date', 'study_period', 'exposure', 'needs_review')
    list_filter = ('xml_form_id', 'needs_review', 'facility')
    search_fields = ('study_id', 'instance_id')
    inlines = [DerivedScoreInline]

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(DerivedScore)
class DerivedScoreAdmin(admin.ModelAdmin):
    list_display = ('submission', 'variable', 'number_value', 'text_value')
    list_filter = ('variable', 'number_value')

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False
