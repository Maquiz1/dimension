"""The DIMENSION study-progress presentation, written once as data and drawn two ways:
the web page (templates/dimension/presentation.html) and PowerPoint (build_pptx below).

Figures come from study.summary, the same as the dashboard. Counts only: no participant is identified.
Slide types: cover, cards, wedge, stats, bars, end.
"""
from io import BytesIO

from django.utils import timezone

# DIMENSION colours, as on the flyer and the inception slides
INK, BODY, MUTED, PAPER, MIST = '14303A', '3D5560', '6A7F88', 'F6F4EE', 'E6EDEB'
TEAL, TEAL_SOFT, AMBER, ALERT = '1F5F6B', 'D4E6E6', 'E3A23B', 'A8432E'


def build_deck(summary):
    s = summary
    regions = dict(s['regions'])
    mh_units = sum(f.has_mental_health_unit for f in s['facilities'])
    form_stats = [{'value': f['total'], 'label': f'{f["name"]} submissions'} for f in s['forms']]
    slides = [
        {'type': 'cover', 'nav': 'Cover', 'kicker': 'NIMR · DIMENSION study', 'title': 'DIMENSION',
         'subtitle': 'Study progress',
         'lead': 'Digital mental health training for health workers in 20 HIV clinics in Dar es Salaam and Mwanza, '
                 'evaluated in a stepped-wedge cluster randomised trial.',
         'stats': [{'value': s['clinic_count'], 'label': 'clinics'},
                   {'value': f"{s['allocated_count']} / {s['clinic_count']}", 'label': 'clinics allocated to a sequence'},
                   {'value': s['submission_count'], 'label': 'form submissions received'}]},

        {'type': 'cards', 'nav': 'The study', 'kicker': 'Design', 'title': 'How the trial works', 'cards': [
            {'title': 'Stepped wedge', 'text': '20 clinics in 5 sequences of 4. All start in control and switch to the '
                                               'intervention one sequence at a time, over 8 periods of 3 months.'},
            {'title': 'Primary outcome', 'text': 'Health workers’ attitudes and confidence in depression care (R-DAQ), '
                                                 'in a cohort of about 60 health workers assessed every period.'},
            {'title': 'Patients', 'text': 'New patients each period are screened with PHQ-9 and GAD-7; scores of 10 or '
                                          'more are referred for diagnosis.'},
            {'title': 'Data', 'text': 'Collected on tablets, scored on the server, and held under NIMR’s control.'},
        ]},

        {'type': 'wedge', 'nav': 'Rollout', 'kicker': 'Allocation', 'title': 'Stepped-wedge rollout',
         'lead': 'C = control (usual care), I = intervention. ' + (
             'Clinics as allocated by the statistician.' if s['allocated_count'] else 'Allocation still to come.'),
         'periods': s['periods'], 'rows': s['wedge'], 'current_period': s['current_period']},

        {'type': 'stats', 'nav': 'Clinics', 'kicker': 'Sites', 'title': 'The 20 clinics', 'stats': [
            {'value': regions.get('Dar es Salaam', 0), 'label': 'in Dar es Salaam'},
            {'value': regions.get('Mwanza', 0), 'label': 'in Mwanza'},
            {'value': mh_units, 'label': 'with a mental health unit'},
            {'value': f"{s['allocated_count']} / {s['clinic_count']}", 'label': 'allocated to a sequence'}]},

        {'type': 'stats', 'nav': 'Data', 'kicker': 'Data collection', 'title': 'Forms received so far',
         'stats': [{'value': s['submission_count'], 'label': 'submissions in total'}, *form_stats,
                   {'value': s['review_count'], 'label': 'flagged for review'}]},

        {'type': 'bars', 'nav': 'Severity', 'kicker': 'Screening', 'title': 'Depression and anxiety severity',
         'lead': 'Scores of 10 or more are referred to a clinician.',
         'charts': [{'title': 'PHQ-9 (depression)', 'rows': s['phq_bands']},
                    {'title': 'GAD-7 (anxiety)', 'rows': s['gad_bands']}]},

        {'type': 'stats', 'nav': 'Safety', 'kicker': 'Participant safety', 'title': 'Safety alerts',
         'lead': 'Any thought of death or self-harm on PHQ-9 item 9 means immediate referral to the study psychiatrist.',
         'stats': [{'value': s['item9_alerts'], 'label': 'PHQ-9 item 9 alerts', 'alert': True},
                   {'value': s['review_count'], 'label': 'records flagged for review'}]},

        {'type': 'end', 'nav': 'Thank you', 'kicker': 'NIMR · DIMENSION study', 'title': 'Asante sana. Thank you.',
         'lead': 'dimension.tamris.org'},
    ]
    return {'slides': slides, 'asof': timezone.localtime()}


# ── PowerPoint ──────────────────────────────────────────────────────────────

def build_pptx(deck):
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Emu, Pt

    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)
    blank = prs.slide_layouts[6]
    W, M = 12192000, 812800

    def rgb(hexstr):
        return RGBColor.from_string(hexstr)

    def box(slide, x, y, w, h, fill):
        shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(x), Emu(y), Emu(w), Emu(h))
        shape.fill.solid()
        shape.fill.fore_color.rgb = rgb(fill)
        shape.line.fill.background()
        shape.shadow.inherit = False
        return shape

    def text(slide, x, y, w, h, value, size, color, bold=False, serif=False, align=None):
        tb = slide.shapes.add_textbox(Emu(x), Emu(y), Emu(w), Emu(h))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = str(value)
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = rgb(color)
        run.font.name = 'Source Serif 4' if serif else 'Public Sans'
        if align:
            p.alignment = align
        return tb

    def background(slide, color):
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = rgb(color)

    def heading(slide, s, dark=False):
        text(slide, M, 560000, W - 2 * M, 300000, s['kicker'].upper(), 12, AMBER if dark else TEAL, bold=True)
        text(slide, M, 900000, W - 2 * M, 600000, s['title'], 30, PAPER if dark else INK, bold=True, serif=True)
        if s.get('lead'):
            text(slide, M, 1560000, W - 2 * M, 400000, s['lead'], 14, BODY)

    def stat_row(slide, stats, y, dark=False):
        n = len(stats)
        gap = 228600
        w = (W - 2 * M - gap * (n - 1)) // n
        for i, st in enumerate(stats):
            x = M + i * (w + gap)
            box(slide, x, y, w, 1300000, '1E4450' if dark else MIST)
            box(slide, x, y, w, 50800, ALERT if st.get('alert') else (AMBER if dark else TEAL))
            text(slide, x + 228600, y + 228600, w - 457200, 600000, st['value'], 36,
                 PAPER if dark else INK, bold=True, serif=True)
            text(slide, x + 228600, y + 850000, w - 457200, 350000, st['label'], 13, 'C9DAD8' if dark else BODY)

    def footer(slide, n, dark=False):
        text(slide, M, 6350000, 6000000, 250000,
             f"DIMENSION study progress · as of {deck['asof']:%d %b %Y}", 10, 'C9DAD8' if dark else MUTED)
        text(slide, W - M - 600000, 6350000, 600000, 250000, n, 10, 'C9DAD8' if dark else MUTED, align=PP_ALIGN.RIGHT)

    for n, s in enumerate(deck['slides'], 1):
        slide = prs.slides.add_slide(blank)
        kind = s['type']
        if kind in ('cover', 'end'):
            background(slide, INK)
            text(slide, M, 900000, W - 2 * M, 300000, s['kicker'].upper(), 12, AMBER, bold=True)
            text(slide, M, 1350000, W - 2 * M, 900000, s['title'], 48, PAPER, bold=True, serif=True)
            if kind == 'cover':
                text(slide, M, 2250000, W - 2 * M, 500000, s['subtitle'], 28, AMBER, bold=True, serif=True)
                text(slide, M, 2900000, W - 2 * M, 700000, s['lead'], 16, 'C9DAD8')
                stat_row(slide, s['stats'], 4000000, dark=True)
            else:
                text(slide, M, 2500000, W - 2 * M, 400000, s['lead'], 18, 'C9DAD8')
            footer(slide, n, dark=True)
            continue

        background(slide, PAPER)
        heading(slide, s)
        top = 2150000 if s.get('lead') else 1800000
        if kind == 'cards':
            gap, cw, ch = 228600, (W - 2 * M - 228600) // 2, 1750000
            for i, c in enumerate(s['cards']):
                x, y = M + (i % 2) * (cw + gap), top + (i // 2) * (ch + gap)
                box(slide, x, y, cw, ch, MIST)
                box(slide, x, y, cw, 50800, TEAL)
                text(slide, x + 254000, y + 254000, cw - 508000, 350000, c['title'], 17, INK, bold=True)
                text(slide, x + 254000, y + 680000, cw - 508000, 950000, c['text'], 14, BODY)
        elif kind == 'stats':
            stat_row(slide, s['stats'], top + 200000)
        elif kind == 'wedge':
            periods = s['periods']
            label_w, clinics_w = 1100000, 3600000
            cell_w = (W - 2 * M - label_w - clinics_w) // len(periods)
            row_h = 560000
            text(slide, M, top, label_w, 300000, 'Sequence', 12, MUTED, bold=True)
            for j, p in enumerate(periods):
                text(slide, M + label_w + j * cell_w, top, cell_w, 300000, f'P{p}', 12, MUTED, bold=True, align=PP_ALIGN.CENTER)
            text(slide, M + label_w + len(periods) * cell_w + 152400, top, clinics_w, 300000, 'Clinics', 12, MUTED, bold=True)
            for i, row in enumerate(s['rows']):
                y = top + 350000 + i * (row_h + 38100)
                text(slide, M, y + 150000, label_w, 300000, row['sequence'], 16, INK, bold=True)
                for j, cell in enumerate(row['cells']):
                    x = M + label_w + j * cell_w
                    box(slide, x + 12700, y, cell_w - 25400, row_h, AMBER if cell['intervention'] else TEAL_SOFT)
                    text(slide, x, y + 150000, cell_w, 300000, 'I' if cell['intervention'] else 'C', 14,
                         INK if cell['intervention'] else TEAL, bold=True, align=PP_ALIGN.CENTER)
                text(slide, M + label_w + len(periods) * cell_w + 152400, y + 60000, clinics_w - 152400, row_h,
                     ', '.join(row['clinics']) or 'Awaiting allocation', 11, BODY)
        elif kind == 'bars':
            gap, cw = 228600, (W - 2 * M - 228600) // 2
            for i, chart in enumerate(s['charts']):
                x = M + i * (cw + gap)
                box(slide, x, top, cw, 3700000, MIST)
                text(slide, x + 254000, top + 228600, cw - 508000, 350000, chart['title'], 17, INK, bold=True)
                track_x, track_w = x + 2300000, cw - 2300000 - 700000
                for k, r in enumerate(chart['rows']):
                    y = top + 800000 + k * 540000
                    text(slide, x + 254000, y, 2000000, 300000, f"{r['label']} ({r['range']})", 12, BODY)
                    box(slide, track_x, y + 40000, track_w, 200000, TEAL_SOFT)
                    if r['width']:
                        box(slide, track_x, y + 40000, max(track_w * r['width'] // 100, 12700), 200000, TEAL)
                    text(slide, track_x + track_w + 127000, y, 500000, 300000, r['count'], 13, INK, bold=True)
        footer(slide, n)

    out = BytesIO()
    prs.save(out)
    return out.getvalue()
