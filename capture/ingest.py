from datetime import date

from django.db import transaction
from django.utils.dateparse import parse_datetime

from study.models import Facility, exposure_for

from .models import DerivedScore, FormSubmission
from .scoring import RULE_VERSION, SCORERS


def _parse_date(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


@transaction.atomic
def ingest_record(xml_form_id, record):
    """Store one OData record and recalculate from it. Safe to repeat for the same record."""
    system = record.get('__system') or {}
    answers = {k: v for k, v in record.items() if not k.startswith('__')}
    problems = []

    study_id = str(answers.get('study_id') or '').strip()
    if not study_id:
        problems.append('Missing study_id.')

    facility = Facility.objects.filter(pk=answers.get('facility_code')).first()
    if facility is None:
        problems.append(f"Unknown facility code {answers.get('facility_code')!r}.")

    visit_date = _parse_date(answers.get('visit_date'))
    if visit_date is None:
        problems.append('Missing or invalid visit_date.')

    period = exposure = None
    if facility and visit_date:
        period, exposure = exposure_for(facility, visit_date)

    submitted = system.get('submissionDate')
    submission, _ = FormSubmission.objects.update_or_create(
        instance_id=record['__id'],
        defaults={
            'xml_form_id': xml_form_id,
            'form_version': system.get('formVersion') or '',
            'answers': answers,
            'submitted_at': parse_datetime(submitted) if submitted else None,
            'study_id': study_id,
            'facility': facility,
            'visit_date': visit_date,
            'study_period': period,
            'exposure': exposure,
        },
    )

    submission.scores.all().delete()
    scores = SCORERS[xml_form_id](answers)
    for variable, value in scores.items():
        DerivedScore.objects.create(
            submission=submission,
            variable=variable,
            number_value=value if isinstance(value, int) else None,
            text_value=value if isinstance(value, str) else '',
            rule_version=RULE_VERSION,
        )
    if any(name.endswith('_total') and value is None for name, value in scores.items()):
        problems.append('Scale incomplete or has an out-of-range answer; total not calculated.')

    submission.needs_review = bool(problems)
    submission.review_reason = ' '.join(problems)
    submission.save(update_fields=['needs_review', 'review_reason'])
    return submission
