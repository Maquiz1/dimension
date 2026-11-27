"""Form submissions inside the study system (read only: corrections are made in ODK Central)."""
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Prefetch
from django.shortcuts import get_object_or_404, render

from capture.models import DerivedScore, FormSubmission

from . import design
from .access import staff_required
from .models import Facility
from .summary import FORM_NAMES

PER_PAGE = 50
EXPOSURE_NAMES = {design.CONTROL: 'Control', design.INTERVENTION: 'Intervention'}
SCORE_NAMES = {
    'phq_total': 'PHQ-9 total', 'phq_band': 'PHQ-9 severity', 'phq_refer': 'PHQ-9 referral (≥ 10)',
    'phq_item9_alert': 'PHQ-9 item 9 safety alert',
    'gad_total': 'GAD-7 total', 'gad_band': 'GAD-7 severity', 'gad_refer': 'GAD-7 referral (≥ 10)',
}


def _alert_exists():
    return Exists(DerivedScore.objects.filter(submission=OuterRef('pk'), variable='phq_item9_alert', number_value=1))


def _score_value(score):
    if score.number_value is not None:
        if score.variable.endswith(('_refer', '_alert')):
            return 'Yes' if score.number_value else 'No'
        return score.number_value
    return score.text_value.replace('_', ' ').capitalize() if score.text_value else '–'


def _flatten(answers, prefix=''):
    """ODK groups arrive as nested objects; show them as group / question."""
    for key, value in answers.items():
        if key.startswith('__'):
            continue
        name = f'{prefix}{key}'
        if isinstance(value, dict):
            yield from _flatten(value, f'{name} / ')
        elif isinstance(value, list):
            yield name, f'{len(value)} repeat{"s" if len(value) != 1 else ""}'
        else:
            yield name, value


@staff_required
def submissions(request):
    params = {key: request.GET.get(key, '').strip() for key in ('form', 'clinic', 'period', 'status', 'q')}
    qs = (FormSubmission.objects.select_related('facility').annotate(item9=_alert_exists())
          .prefetch_related(Prefetch('scores', queryset=DerivedScore.objects.filter(variable__endswith='_total'))))
    if params['form']:
        qs = qs.filter(xml_form_id=params['form'])
    if params['clinic']:
        qs = qs.filter(facility__code=params['clinic'])
    if params['period'].isdigit():
        qs = qs.filter(study_period=int(params['period']))
    elif params['period'] == 'none':
        qs = qs.filter(study_period__isnull=True)
    if params['status'] == 'review':
        qs = qs.filter(needs_review=True)
    elif params['status'] == 'item9':
        qs = qs.filter(item9=True)
    if params['q']:
        qs = qs.filter(study_id__icontains=params['q'])
    qs = qs.order_by('-submitted_at', '-pk')

    page = Paginator(qs, PER_PAGE).get_page(request.GET.get('page'))
    rows = [{
        's': s, 'form': FORM_NAMES.get(s.xml_form_id, s.xml_form_id),
        'exposure': EXPOSURE_NAMES.get(s.exposure),
        'total': next((score.number_value for score in s.scores.all()), None),
    } for s in page]
    query = request.GET.copy()
    query.pop('page', None)
    forms = sorted(set(FormSubmission.objects.values_list('xml_form_id', flat=True)) | set(FORM_NAMES))
    return render(request, 'study/submissions.html', {
        'rows': rows, 'page': page, 'query': query.urlencode(), 'filtered': any(params.values()),
        'forms': [(f, FORM_NAMES.get(f, f)) for f in forms],
        'clinics': Facility.objects.order_by('code'), 'periods': design.PERIODS,
        'total': FormSubmission.objects.count(), **params,
    })


@staff_required
def submission_detail(request, pk):
    s = get_object_or_404(FormSubmission.objects.select_related('facility'), pk=pk)
    scores = [{'label': SCORE_NAMES.get(sc.variable, sc.variable), 'value': _score_value(sc),
               'alert': sc.variable == 'phq_item9_alert' and sc.number_value == 1, 'rule': sc.rule_version}
              for sc in s.scores.order_by('variable')]
    answers = sorted(_flatten(s.answers))
    return render(request, 'study/submission_detail.html', {
        's': s, 'form': FORM_NAMES.get(s.xml_form_id, s.xml_form_id), 'exposure': EXPOSURE_NAMES.get(s.exposure),
        'scores': scores, 'answers': answers, 'item9': any(sc['alert'] for sc in scores),
    })
