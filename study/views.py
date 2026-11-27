from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from resources.models import SlideDeck

from .access import staff_required
from .presentation import build_deck, build_pptx
from .summary import study_summary


@staff_required
def dashboard(request):
    return render(request, 'study/dashboard.html', study_summary())


@staff_required
def presentation(request):
    """Choose what to present: the live study-progress deck, or a deck kept in Resources (its latest file)."""
    decks = SlideDeck.objects.select_related('slides', 'notes')
    return render(request, 'dimension/presentation_choose.html', {'decks': decks})


@staff_required
def presentation_live(request):
    return render(request, 'dimension/presentation.html', {'deck': build_deck(study_summary())})


@staff_required
def presentation_pptx(request):
    deck = build_deck(study_summary())
    response = HttpResponse(
        build_pptx(deck), content_type='application/vnd.openxmlformats-officedocument.presentationml.presentation')
    response['Content-Disposition'] = f'attachment; filename="DIMENSION_study_progress_{deck["asof"]:%Y-%m-%d}.pptx"'
    return response


@staff_required
def slideshow(request, key):
    """Present a deck's PDF full screen, whatever version its Resources entry holds now."""
    deck = get_object_or_404(SlideDeck.objects.select_related('slides', 'notes'), key=key)
    if not deck.slides.is_pdf:
        raise Http404('This presentation has no PDF to show.')
    return render(request, 'dimension/slideshow.html', {
        'deck': deck,
        'pdf_url': reverse('resources:preview', args=[deck.slides.pk]),
        'notes_url': reverse('resources:detail', args=[deck.notes.pk]) if deck.notes else '',
    })
