"""Study progress figures, shared by the dashboard and the presentation so both always agree.
Counts only: nothing here identifies a participant."""
from datetime import date

from django.db.models import Count, Max, Q

from capture.models import DerivedScore, FormSubmission
from capture.scoring import GAD_BANDS, PHQ_BANDS

from . import design
from .models import Facility, StudyPeriod

FORM_NAMES = {
    'dim_5p_phq9': 'PHQ-9 (5P)',
    'dim_6p_gad7': 'GAD-7 (6P)',
}


def _band_rows(variable, bands):
    """Count submissions per severity band, in the scale's order, with bar widths."""
    counts = dict(
        DerivedScore.objects.filter(variable=variable)
        .values_list('text_value')
        .annotate(n=Count('id'))
    )
    largest = max(counts.values(), default=0)
    return [
        {
            'label': label.replace('_', ' ').capitalize(),
            'range': f'{low}–{high}',
            'count': counts.get(label, 0),
            'width': round(100 * counts.get(label, 0) / largest) if largest else 0,
        }
        for low, high, label in bands
    ]


def alert_counts():
    """The two counts the navbar bell shows."""
    return {
        'item9_alerts': DerivedScore.objects.filter(variable='phq_item9_alert', number_value=1).count(),
        'review_count': FormSubmission.objects.filter(needs_review=True).count(),
    }


def study_summary():
    # Explicit order: Django drops Meta.ordering from queries that group by an annotation.
    facilities = list(Facility.objects.annotate(submissions=Count('formsubmission')).order_by('region', 'code'))
    allocated = [f for f in facilities if f.sequence is not None]

    regions = {}
    for facility in facilities:
        regions[facility.region] = regions.get(facility.region, 0) + 1

    wedge = []
    for sequence in design.SEQUENCES:
        wedge.append({
            'sequence': sequence,
            'start': design.first_intervention_period(sequence),
            'cells': [
                {'period': p, 'intervention': design.exposure(sequence, p) == design.INTERVENTION}
                for p in design.PERIODS
            ],
            'clinics': [f.name for f in allocated if f.sequence == sequence],
        })

    forms = []
    for xml_form_id, name in FORM_NAMES.items():
        stats = FormSubmission.objects.filter(xml_form_id=xml_form_id).aggregate(
            total=Count('id'),
            review=Count('id', filter=Q(needs_review=True)),
            latest=Max('submitted_at'),
        )
        forms.append({'name': name, **stats})

    return {
        'facilities': facilities,
        'clinic_count': len(facilities),
        'regions': sorted(regions.items()),
        'allocated_count': len(allocated),
        'periods': list(design.PERIODS),
        'current_period': StudyPeriod.number_for(date.today()),
        'periods_defined': StudyPeriod.objects.exists(),
        'wedge': wedge,
        'forms': forms,
        'submission_count': FormSubmission.objects.count(),
        **alert_counts(),
        'phq_bands': _band_rows('phq_band', PHQ_BANDS),
        'gad_bands': _band_rows('gad_band', GAD_BANDS),
    }
