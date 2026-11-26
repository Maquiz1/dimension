import shutil
import tempfile

from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import StudyDocument

MEDIA = tempfile.mkdtemp()


def pdf(name='protocol.pdf'):
    return SimpleUploadedFile(name, b'%PDF-1.4 test', content_type='application/pdf')


@override_settings(MEDIA_ROOT=MEDIA)
class ResourcesTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.viewer = User.objects.create_user('viewer', password='x', is_staff=True)
        self.manager = User.objects.create_user('manager', password='x', is_staff=True)
        self.manager.user_permissions.add(*Permission.objects.filter(
            codename__in=['add_studydocument', 'change_studydocument', 'delete_studydocument']))
        self.document = StudyDocument.objects.create(title='Protocol', category='protocol', version='V2', file=pdf())

    def upload(self, **data):
        fields = {'title': 'Flyer', 'category': 'presentation', 'version': '', 'description': '', 'file': pdf('flyer.pdf')}
        fields.update(data)
        return self.client.post(reverse('resources:create'), fields)

    def test_staff_only(self):
        for name in ('resources:list', 'resources:create'):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302)
            self.assertIn('/login/?next=', response['Location'])
        response = self.client.get(reverse('resources:download', args=[self.document.pk]))
        self.assertIn('/login/?next=', response['Location'])

    def test_list_counts_and_filters(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('resources:list'), {'category': 'protocol', 'q': 'proto'})
        self.assertContains(response, 'Protocol')
        self.assertEqual(response.context['total_count'], 1)
        self.assertNotContains(response, 'Upload a document')

    def test_viewer_cannot_upload(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.upload().status_code, 403)
        self.assertFalse(StudyDocument.objects.filter(title='Flyer').exists())

    def test_manager_uploads(self):
        self.client.force_login(self.manager)
        response = self.upload()
        document = StudyDocument.objects.get(title='Flyer')
        self.assertRedirects(response, reverse('resources:detail', args=[document.pk]))
        self.assertEqual(document.uploaded_by, self.manager)

    def test_rejects_html_and_duplicate_titles(self):
        self.client.force_login(self.manager)
        response = self.upload(file=SimpleUploadedFile('page.html', b'<script></script>', content_type='text/html'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(StudyDocument.objects.filter(title='Flyer').exists())
        response = self.upload(title='protocol')
        self.assertContains(response, 'already exists')

    def test_pdf_preview_inline_but_download_is_attachment(self):
        self.client.force_login(self.viewer)
        preview = self.client.get(reverse('resources:preview', args=[self.document.pk]))
        self.assertTrue(preview['Content-Disposition'].startswith('inline'))
        self.assertEqual(preview['X-Content-Type-Options'], 'nosniff')
        download = self.client.get(reverse('resources:download', args=[self.document.pk]))
        self.assertTrue(download['Content-Disposition'].startswith('attachment'))

    def test_non_pdf_preview_is_downloaded(self):
        sheet = StudyDocument.objects.create(
            title='Dictionary', file=SimpleUploadedFile('d.xlsx', b'xlsx', content_type='application/octet-stream'))
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('resources:preview', args=[sheet.pk]))
        self.assertTrue(response['Content-Disposition'].startswith('attachment'))

    def test_delete_removes_file(self):
        storage, name = self.document.file.storage, self.document.file.name
        self.client.force_login(self.manager)
        self.client.post(reverse('resources:delete', args=[self.document.pk]))
        self.assertFalse(StudyDocument.objects.exists())
        self.assertFalse(storage.exists(name))
