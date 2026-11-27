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


@override_settings(MEDIA_ROOT=MEDIA)
class SlideDeckTests(TestCase):
    def setUp(self):
        from .models import SlideDeck

        self.manager = User.objects.create_user('manager', password='x', is_staff=True)
        self.manager.user_permissions.add(*Permission.objects.filter(
            codename__in=['add_studydocument', 'change_studydocument', 'delete_studydocument']))
        self.slides = StudyDocument.objects.create(title='Simple slides', category='presentation', version='v5', file=pdf('s.pdf'))
        self.notes = StudyDocument.objects.create(title='Simple notes', category='presentation', version='v5', file=pdf('n.pdf'))
        self.deck = SlideDeck.objects.create(key='inception-simple', title='Inception meeting: simple version',
                                             slides=self.slides, notes=self.notes)
        self.client.force_login(self.manager)

    def test_choose_page_lists_live_and_latest_version(self):
        response = self.client.get('/presentation/')
        self.assertContains(response, 'Live study progress')
        self.assertContains(response, 'Inception meeting: simple version')
        self.assertContains(response, 'v5')
        self.assertContains(response, '/presentation/inception-simple/')

    def test_slideshow_shows_the_file_the_entry_holds_now(self):
        response = self.client.get('/presentation/inception-simple/')
        self.assertContains(response, reverse('resources:preview', args=[self.slides.pk]))
        self.client.post(reverse('resources:update', args=[self.slides.pk]),
                         {'title': 'Simple slides', 'category': 'presentation', 'version': 'v6', 'description': '', 'file': pdf('s6.pdf')})
        self.assertContains(self.client.get('/presentation/'), 'v6')   # same deck, new version, nothing else to change

    def test_presented_slides_cannot_be_deleted_or_replaced_by_non_pdf(self):
        name = self.slides.file.name
        response = self.client.post(reverse('resources:delete', args=[self.slides.pk]))
        self.assertRedirects(response, reverse('resources:detail', args=[self.slides.pk]))
        self.assertTrue(StudyDocument.objects.filter(pk=self.slides.pk).exists())
        self.assertTrue(self.slides.file.storage.exists(name))
        response = self.client.post(reverse('resources:update', args=[self.slides.pk]), {
            'title': 'Simple slides', 'category': 'presentation', 'version': 'v6', 'description': '',
            'file': SimpleUploadedFile('s.pptx', b'pptx', content_type='application/octet-stream')})
        self.assertContains(response, 'must be a PDF')

    def test_non_pdf_deck_cannot_be_presented(self):
        StudyDocument.objects.filter(pk=self.slides.pk).update(file='resources/s.xlsx')
        self.assertEqual(self.client.get('/presentation/inception-simple/').status_code, 404)

    def test_migration_links_the_inception_decks(self):
        from importlib import import_module

        from django.apps import apps

        from .models import SlideDeck
        SlideDeck.objects.all().delete()
        StudyDocument.objects.create(title='Inception meeting presentation: digital technology and ethics', file=pdf('d.pdf'))
        StudyDocument.objects.create(title='Inception meeting presentation: speaker notes', file=pdf('dn.pdf'))
        StudyDocument.objects.create(title='Inception meeting presentation: simple version', file=pdf('s.pdf'))
        import_module('resources.migrations.0003_inception_decks').link(apps, None)
        detailed = SlideDeck.objects.get(key='inception-detailed')
        self.assertEqual(detailed.slides.title, 'Inception presentation: detailed version')
        self.assertEqual(detailed.notes.title, 'Inception presentation: detailed version speaker notes')
        self.assertEqual(SlideDeck.objects.get(key='inception-simple').slides.title, 'Inception presentation: simple version')
