"""Link the two inception-meeting decks to their Resources entries and give those entries clear titles.
Only acts where the entries exist (the live server); elsewhere it does nothing."""
from django.db import migrations

DECKS = [
    # key, deck title, order, (old slides title, new slides title), (old notes title, new notes title)
    ('inception-detailed', 'Inception meeting: detailed version', 1,
     ('Inception meeting presentation: digital technology and ethics', 'Inception presentation: detailed version'),
     ('Inception meeting presentation: speaker notes', 'Inception presentation: detailed version speaker notes')),
    ('inception-simple', 'Inception meeting: simple version', 2,
     ('Inception meeting presentation: simple version', 'Inception presentation: simple version'),
     ('Inception meeting presentation: simple version speaker notes', 'Inception presentation: simple version speaker notes')),
]


def _entry(Document, old, new):
    doc = Document.objects.filter(title=old).first() or Document.objects.filter(title=new).first()
    if doc and doc.title != new:
        doc.title = new
        doc.save(update_fields=['title'])
    return doc


def link(apps, schema_editor):
    Document = apps.get_model('resources', 'StudyDocument')
    SlideDeck = apps.get_model('resources', 'SlideDeck')
    for key, title, order, slides, notes in DECKS:
        slides_doc = _entry(Document, *slides)
        notes_doc = _entry(Document, *notes)
        if slides_doc and not SlideDeck.objects.filter(key=key).exists():
            SlideDeck.objects.create(key=key, title=title, order=order, slides=slides_doc, notes=notes_doc,
                                     description='Use of digital technology and ethical concerns, 27 November 2026.')


class Migration(migrations.Migration):
    dependencies = [('resources', '0002_slidedeck')]
    operations = [migrations.RunPython(link, migrations.RunPython.noop)]
