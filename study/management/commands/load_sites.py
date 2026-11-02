from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from openpyxl import load_workbook

from study.design import allocation_errors
from study.models import Facility

HEADER_ROW = 2
EXPECTED_HEADERS = [
    'Facility code', 'Clinic', 'Facility type', 'Ward', 'Clients', 'Region', 'District',
    'Selection method', 'Mental health unit (per plan)', 'Sequence (1-5)',
]


def read_sites(path):
    sheet = load_workbook(path, data_only=True)['Sites']
    headers = [cell.value for cell in sheet[HEADER_ROW]][:len(EXPECTED_HEADERS)]
    if headers != EXPECTED_HEADERS:
        raise CommandError(f'Unexpected Sites headers: {headers}')
    sites = []
    for row in sheet.iter_rows(min_row=HEADER_ROW + 1, max_col=len(EXPECTED_HEADERS), values_only=True):
        if not row[1]:
            continue
        sites.append({
            'code': row[0],
            'name': row[1],
            'facility_type': row[2],
            'ward': row[3],
            'clients': row[4],
            'region': row[5],
            'district': row[6].rstrip('*'),
            'selection_method': row[7],
            'has_mental_health_unit': row[8] == 'Yes',
            'sequence': row[9],
        })
    return sites


class Command(BaseCommand):
    help = 'Load the confirmed clinics, and the allocation once it is in the workbook.'

    def add_arguments(self, parser):
        parser.add_argument('--path', default=settings.DATA_DICTIONARY_PATH)

    @transaction.atomic
    def handle(self, *args, **options):
        if not Path(options['path']).exists():
            raise CommandError(f"Data dictionary not found at {options['path']}. It is not in git; see README.")
        sites = read_sites(options['path'])
        allocation = {s['code']: s['sequence'] for s in sites if s['sequence'] is not None}
        if allocation:
            errors = allocation_errors(allocation)
            if errors:
                raise CommandError('Allocation not loaded. ' + ' '.join(errors))
        for site in sites:
            existing = Facility.objects.filter(pk=site['code']).first()
            if existing and existing.sequence is not None and existing.sequence != site['sequence']:
                raise CommandError(
                    f"{site['code']} is already allocated to sequence {existing.sequence}. "
                    'A loaded allocation cannot be changed by this command.'
                )
            Facility.objects.update_or_create(code=site['code'], defaults=site)
        state = 'with allocation' if allocation else 'without allocation (waiting for statistician)'
        self.stdout.write(self.style.SUCCESS(f'Loaded {len(sites)} clinics {state}.'))
