import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models

# Office documents, PDFs and plain text. No HTML, SVG or scripts: files are served from this site.
ALLOWED_EXTENSIONS = ['pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'odt', 'odp', 'ods', 'csv', 'txt']
MAX_UPLOAD_MB = 50


def validate_file_size(file):
    if file.size > MAX_UPLOAD_MB * 1024 * 1024:
        raise ValidationError(f'The file is too large; the limit is {MAX_UPLOAD_MB} MB.')


class StudyDocument(models.Model):
    """A study document staff can preview or download: protocol, tools, SOPs, presentations."""

    CATEGORY_CHOICES = [
        ('protocol', 'Protocol and approvals'),
        ('tools', 'Data collection tools'),
        ('sop', 'SOPs and guides'),
        ('training', 'Training materials'),
        ('presentation', 'Presentations and meetings'),
        ('other', 'Other'),
    ]

    title = models.CharField(max_length=200, unique=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    version = models.CharField(max_length=30, blank=True, help_text='Optional, for example "V2" or "v0.3".')
    description = models.TextField(blank=True, help_text='Optional: what the document covers and who it is for.')
    file = models.FileField(
        upload_to='resources/',
        validators=[FileExtensionValidator(ALLOWED_EXTENSIONS), validate_file_size],
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'title']

    def __str__(self):
        return self.title

    @property
    def extension(self):
        return os.path.splitext(self.file.name)[1].lower().lstrip('.') if self.file else ''

    @property
    def is_pdf(self):
        return self.extension == 'pdf'

    @property
    def file_size(self):
        """Size in bytes, or None if the file is missing from storage."""
        try:
            return self.file.size
        except (FileNotFoundError, OSError, ValueError):
            return None

    @property
    def download_name(self):
        """The title as a file name, keeping the original extension."""
        safe = ''.join(c if c.isalnum() or c in ' -_.()' else '_' for c in self.title).strip() or 'document'
        return f'{safe}.{self.extension}' if self.extension else safe


class SlideDeck(models.Model):
    """A presentation people can choose to present. It points at a Resources entry, so whatever file that entry
    holds now (replaced there with each new version) is what gets presented."""

    key = models.SlugField(unique=True, help_text='Short name used in the web address, e.g. inception-simple.')
    title = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True)
    slides = models.ForeignKey(
        StudyDocument, on_delete=models.PROTECT, related_name='+',
        help_text='The Resources entry with the slides as a PDF. Replace the file there to update the presentation.',
    )
    notes = models.ForeignKey(
        StudyDocument, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
        help_text='Optional: the Resources entry with the speaker notes.',
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'title']

    def __str__(self):
        return self.title

    def clean(self):
        if self.slides_id and not self.slides.is_pdf:
            raise ValidationError({'slides': 'Only a PDF can be presented. Upload the slides as a PDF in Resources.'})
