from django.http import HttpResponse
from django.shortcuts import render

from .access import staff_required
from .presentation import build_deck, build_pptx
from .summary import study_summary


@staff_required
def dashboard(request):
    return render(request, 'study/dashboard.html', study_summary())


@staff_required
def presentation(request):
    return render(request, 'dimension/presentation.html', {'deck': build_deck(study_summary())})


@staff_required
def presentation_pptx(request):
    deck = build_deck(study_summary())
    response = HttpResponse(
        build_pptx(deck), content_type='application/vnd.openxmlformats-officedocument.presentationml.presentation')
    response['Content-Disposition'] = f'attachment; filename="DIMENSION_study_progress_{deck["asof"]:%Y-%m-%d}.pptx"'
    return response
