from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from capture.ingest import ingest_record
from capture.odk import CentralClient
from capture.scoring import SCORERS


class Command(BaseCommand):
    help = 'Pull submissions from ODK Central into the database. Safe to run repeatedly.'

    def add_arguments(self, parser):
        parser.add_argument('--form', choices=sorted(SCORERS), help='Pull one form; default is all.')

    def handle(self, *args, **options):
        if not all([settings.ODK_URL, settings.ODK_EMAIL, settings.ODK_PASSWORD, settings.ODK_PROJECT_ID]):
            raise CommandError('Set ODK_URL, ODK_EMAIL, ODK_PASSWORD and ODK_PROJECT_ID in .env.')
        client = CentralClient(
            settings.ODK_URL, settings.ODK_EMAIL, settings.ODK_PASSWORD,
            settings.ODK_PROJECT_ID, settings.ODK_VERIFY_TLS,
        )
        for xml_form_id in ([options['form']] if options['form'] else sorted(SCORERS)):
            total = review = 0
            for record in client.submissions(xml_form_id):
                submission = ingest_record(xml_form_id, record)
                total += 1
                review += submission.needs_review
            self.stdout.write(f'{xml_form_id}: {total} submissions, {review} need review.')
