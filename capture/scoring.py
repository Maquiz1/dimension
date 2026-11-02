"""Server-side scoring. The tablet totals are display-only; these values are the record.

Rules are from the Derived Scores sheet of the data dictionary. The >= 10 referral rule
(decision D03), the 0-4 PHQ-9 band (D34) and the item 9 alert (D04) are still draft.
"""
RULE_VERSION = 'v0.1-draft'
REFERRAL_THRESHOLD = 10

PHQ_BANDS = [(0, 4, 'minimal'), (5, 9, 'mild'), (10, 14, 'moderate'),
             (15, 19, 'moderately_severe'), (20, 27, 'severe')]
GAD_BANDS = [(0, 4, 'minimal'), (5, 9, 'mild'), (10, 14, 'moderate'), (15, 21, 'severe')]


def _item(answers, name):
    """Return a 0-3 answer as an int, or None if missing or out of range. ODK sends text."""
    try:
        value = int(answers.get(name))
    except (TypeError, ValueError):
        return None
    return value if 0 <= value <= 3 else None


def _band(total, bands):
    return next(label for low, high, label in bands if low <= total <= high)


def _score_scale(answers, prefix, count, bands):
    """Totals stay None when any item is missing: a partial sum would understate severity."""
    items = [_item(answers, f'{prefix}_{i:02d}') for i in range(1, count + 1)]
    if None in items:
        return {f'{prefix}_total': None, f'{prefix}_band': None, f'{prefix}_refer': None}
    total = sum(items)
    return {
        f'{prefix}_total': total,
        f'{prefix}_band': _band(total, bands),
        f'{prefix}_refer': int(total >= REFERRAL_THRESHOLD),
    }


def score_phq9(answers):
    scores = _score_scale(answers, 'phq', 9, PHQ_BANDS)
    # Checked on its own so that an incomplete form still raises the alert.
    item9 = _item(answers, 'phq_09')
    scores['phq_item9_alert'] = None if item9 is None else int(item9 > 0)
    return scores


def score_gad7(answers):
    return _score_scale(answers, 'gad', 7, GAD_BANDS)


SCORERS = {
    'dim_5p_phq9': score_phq9,
    'dim_6p_gad7': score_gad7,
}
