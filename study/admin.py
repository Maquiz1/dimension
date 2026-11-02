from django.contrib import admin

from .models import Facility, StudyPeriod


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'facility_type', 'region', 'district', 'clients', 'sequence')
    list_filter = ('region', 'facility_type', 'selection_method')
    search_fields = ('code', 'name')
    # The allocation is loaded from the statistician's file, never typed in.
    readonly_fields = ('sequence',)


@admin.register(StudyPeriod)
class StudyPeriodAdmin(admin.ModelAdmin):
    list_display = ('number', 'start_date', 'end_date')
