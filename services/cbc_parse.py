"""Turning what the laboratory reports into rows of a study table.

Two ways in. A VMACS report-format row, fetched by the browser userscript:
one row per visit, lab columns named CBC_*, a cell holding one value per
panel separated by spaces, comments after a semicolon. And pasted text,
one analyte per line, for when the userscript is not to hand.

Nothing here decides which panel is the pre-release one. It returns every
panel in date order and proposes the latest; the person confirms.
"""

import re
from datetime import date, datetime

_MONTHS = {m: i for i, m in enumerate(
    ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], 1)}

# Labels for the columns we recognise. Anything else keeps the laboratory's
# own name, tidied. No units are asserted here: they are not in the report.
_LABELS = {
    'PCV': 'PCV', 'HCT': 'Hematocrit', 'TP': 'Plasma protein', 'TPP': 'Plasma protein',
    'PP': 'Plasma protein', 'WBC': 'WBC', 'RBC': 'RBC', 'HGB': 'Hemoglobin', 'MCV': 'MCV',
    'MCH': 'MCH', 'MCHC': 'MCHC', 'HET': 'Heterophils', 'HETS': 'Heterophils',
    'HETERO': 'Heterophils', 'HETEROPHILS': 'Heterophils', 'BAND': 'Bands', 'BANDS': 'Bands',
    'LYMPH': 'Lymphocytes', 'LYMPHS': 'Lymphocytes', 'LYMPHOCYTES': 'Lymphocytes',
    'MONO': 'Monocytes', 'MONOS': 'Monocytes', 'MONOCYTES': 'Monocytes',
    'EOS': 'Eosinophils', 'EOSINOPHILS': 'Eosinophils', 'BASO': 'Basophils',
    'BASOS': 'Basophils', 'BASOPHILS': 'Basophils', 'FIB': 'Fibrinogen',
    'FIBRINOGEN': 'Fibrinogen', 'THROMB': 'Thrombocytes', 'THROMBOCYTES': 'Thrombocytes',
}


def analyte_key(name):
    """A stable key from whatever the column or line was called."""
    key = re.sub(r'^CBC[_\s:-]*', '', (name or '').strip(), flags=re.I)
    key = re.sub(r'[^A-Za-z0-9%#]+', '_', key).strip('_').upper()
    return key[:40]


def analyte_label(key):
    if key in _LABELS:
        return _LABELS[key]
    base, _, suffix = key.partition('_')
    if base in _LABELS and suffix:
        tail = {'PCT': '%', 'PERCENT': '%', 'ABS': 'abs', '%': '%', '#': 'abs'}.get(suffix, suffix.lower())
        return f'{_LABELS[base]} {tail}'
    return key.replace('_', ' ').capitalize() if not key.isupper() or len(key) > 5 else key


def to_number(token):
    """A float if the token is a plain number, else None."""
    t = (token or '').strip().replace(',', '')
    if re.fullmatch(r'-?\d+(\.\d+)?', t) or re.fullmatch(r'-?\.\d+', t):
        return float(t)
    return None


def parse_vmacs_date(text):
    """ddMmmyy / ddMmmyyyy, or VMACS's internal 3yymmdd.hhmmss, to a date."""
    t = (text or '').strip()
    m = re.match(r'^(\d{1,2})\s*([A-Za-z]{3})\s*(\d{2,4})', t)
    if m and m.group(2).lower() in _MONTHS:
        year = int(m.group(3))
        if year < 100:
            year += 2000 if year < 70 else 1900
        try:
            return date(year, _MONTHS[m.group(2).lower()], int(m.group(1)))
        except ValueError:
            return None
    m = re.match(r'^3(\d{2})(\d{2})(\d{2})(\.\d+)?$', t)
    if m:
        try:
            return date(2000 + int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y'):
        try:
            return datetime.strptime(t[:10], fmt).date()
        except ValueError:
            continue
    return None


def normalize_sex(text):
    t = (text or '').strip().lower()
    if t.startswith('m'):
        return 'Male'
    if t.startswith('f'):
        return 'Female'
    return 'Unknown'


def digits(text):
    return re.sub(r'\D', '', text or '')


def _col(header, *patterns):
    for i, h in enumerate(header):
        if any(re.search(p, h or '', re.I) for p in patterns):
            return i
    return None


def parse_vmacs_rows(header, rows):
    """header: column names of the report format. rows: one list of cells
    per visit of one patient. Returns demographics and every CBC panel."""
    header = [(h or '').strip() for h in header]
    c_visit = _col(header, r'^visit\s*no', r'^invoice')
    c_patient = _col(header, r'^patient\s*no', r'^ptnt\s*no')
    c_species = _col(header, r'^species')
    c_breed = _col(header, r'^breed')
    c_sex = _col(header, r'^sex')
    c_age = _col(header, r'^age')
    date_cols = [i for i, h in enumerate(header) if re.search(r'date|admit|adms|dsch|disch', h, re.I)]
    cbc_cols = [i for i, h in enumerate(header) if re.match(r'^CBC', h, re.I)]

    def cell(row, i):
        return (row[i] if i is not None and i < len(row) else '') or ''

    visits = []
    for row in rows:
        when = None
        for i in date_cols:
            when = parse_vmacs_date(cell(row, i)) or when
            if when:
                break
        visits.append((when or date.min, digits(cell(row, c_visit)), row))
    visits.sort(key=lambda v: (v[0], v[1]))

    analytes, panels = [], []
    seen = set()
    for when, visit_no, row in visits:
        tokens = {}
        for i in cbc_cols:
            key = analyte_key(header[i])
            if not key:
                continue
            if key not in seen:
                seen.add(key)
                analytes.append({'key': key, 'label': analyte_label(key), 'unit': ''})
            # value(s) first, comment after the semicolon; one token per panel
            main = cell(row, i).split(';', 1)[0].replace('\xa0', ' ').split()
            if main:
                tokens[key] = main
        count = max((len(t) for t in tokens.values()), default=0)
        for p in range(count):
            results = {}
            for key, toks in tokens.items():
                if p < len(toks):
                    num = to_number(toks[p])
                    results[key] = num if num is not None else toks[p][:40]
            if results:
                panels.append({
                    'visit_no': visit_no or None,
                    'collected_on': when.isoformat() if when != date.min else None,
                    'label': f"Visit {visit_no or '?'}" + (f' · {when.isoformat()}' if when != date.min else '')
                             + (f' · panel {p + 1} of {count}' if count > 1 else ''),
                    'results': results,
                })

    last = visits[-1][2] if visits else []
    age = cell(last, c_age).strip()
    age_num = to_number(age)
    numeric = [i for i, p in enumerate(panels)
               if any(isinstance(v, float) for v in p['results'].values())]
    return {
        'patient_no': digits(cell(last, c_patient)) or None,
        'species': cell(last, c_species).strip() or None,
        'breed': cell(last, c_breed).strip() or None,
        'sex': normalize_sex(cell(last, c_sex)),
        'age': (f'{age_num:g} y' if age_num else '') if age_num is not None else age,
        'analytes': analytes,
        'panels': panels,
        'default_panel': numeric[-1] if numeric else (len(panels) - 1 if panels else None),
    }


_LINE = re.compile(r'^\s*(?P<name>[A-Za-z%#][^\t:=]*?)\s*[\t:= ]\s*(?P<value>[<>]?\s*-?\d[\d.,]*)\s*(?P<unit>[^\s\d][^\t]*)?$')


def parse_text(text):
    """Pasted results, one analyte per line: a name, a value, maybe a unit.
    Columns separated by tabs (copied from a table) are honoured first."""
    analytes, results = [], {}
    for raw in (text or '').splitlines():
        line = raw.replace('\xa0', ' ').strip()
        if not line:
            continue
        name = value = unit = None
        if '\t' in line:
            parts = [p.strip() for p in line.split('\t') if p.strip()]
            if len(parts) >= 2:
                name, value = parts[0], parts[1]
                unit = parts[2] if len(parts) > 2 and to_number(parts[2]) is None else ''
        if name is None:
            m = _LINE.match(line)
            if not m:
                continue
            name, value, unit = m.group('name'), m.group('value'), (m.group('unit') or '')
        key = analyte_key(name)
        if not key or key in results:
            continue
        value = value.replace(' ', '')
        num = to_number(value)
        results[key] = num if num is not None else value[:40]
        analytes.append({'key': key, 'label': name.strip()[:60], 'unit': (unit or '').strip()[:20]})
    panels = [{'visit_no': None, 'collected_on': None, 'label': 'Pasted results', 'results': results}] if results else []
    return {'patient_no': None, 'species': None, 'breed': None, 'sex': 'Unknown', 'age': '',
            'analytes': analytes, 'panels': panels, 'default_panel': 0 if panels else None}
