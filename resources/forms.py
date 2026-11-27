from django import forms

from .models import ALLOWED_EXTENSIONS, MAX_UPLOAD_MB, SlideDeck, StudyDocument


class StudyDocumentForm(forms.ModelForm):
    """Upload or edit a document. On edit, leaving the file empty keeps the current one."""

    class Meta:
        model = StudyDocument
        fields = ['title', 'category', 'version', 'description', 'file']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g. DIMENSION Protocol'}),
            'category': forms.RadioSelect(attrs={'class': 'radio'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'file': forms.ClearableFileInput(attrs={'accept': ','.join(f'.{ext}' for ext in ALLOWED_EXTENSIONS)}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['file'].help_text = (
            f'PDF, Word, PowerPoint, Excel, OpenDocument, CSV or text, up to {MAX_UPLOAD_MB} MB.'
            + (' Leave empty to keep the current file.' if self.instance.pk else '')
        )

    def clean_file(self):
        file = self.cleaned_data.get('file')
        replacing = self.instance.pk and file and file != self.instance.file
        if replacing and not file.name.lower().endswith('.pdf') and SlideDeck.objects.filter(slides=self.instance).exists():
            raise forms.ValidationError('This document is used as a presentation, so its replacement must be a PDF.')
        return file

    def clean_title(self):
        title = self.cleaned_data['title'].strip()
        if StudyDocument.objects.exclude(pk=self.instance.pk).filter(title__iexact=title).exists():
            raise forms.ValidationError('A document with this title already exists.')
        return title
