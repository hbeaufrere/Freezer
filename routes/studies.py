"""Research projects. The first kind: CBC reference-interval studies.

A study is a table of birds, one hemogram each, and a set of statistics that
are recomputed from the table every time it is read. Nothing statistical is
stored, so the interval can never disagree with the data under it.
"""

import io
import re
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request, send_file
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from psycopg.types.json import Jsonb

from db import ApiError, get_db
from routes.support import as_date, json_body, one_or_404, text, write
from services import cbc_parse
from services.activity import actor, record
from services.ri_stats import summarize

studies_bp = Blueprint('studies', __name__)

SEXES = ('Male', 'Female', 'Unknown')
MAX_ANALYTES = 80

_ROW = """id, study_id, patient_no, visit_no, wrmd_number, collected_on, age, sex,
          source, results, notes, added_by, created_at"""


def _study(db, slug):
    return one_or_404(db.execute(
        """select id, slug, name, kind, species_code, species_name, description, analytes
           from studies where slug = %s""", (slug,)).fetchone(), 'Study')


def _rows(db, study_id):
    return [dict(r) for r in db.execute(
        f"""select {_ROW} from study_cbcs where study_id = %s
            order by collected_on nulls last, id""", (study_id,)).fetchall()]


def _stats(analytes, rows):
    out = []
    for a in analytes:
        points = [(r['results'][a['key']], {'row_id': r['id'], 'patient_no': r['patient_no']})
                  for r in rows
                  if isinstance(r['results'].get(a['key']), (int, float))
                  and not isinstance(r['results'].get(a['key']), bool)]
        out.append({**a, **summarize(points)})
    return out


@studies_bp.route('/api/studies')
def list_studies():
    rows = get_db().execute(
        """select s.slug, s.name, s.kind, s.species_code, s.species_name, s.description,
                  (select count(*) from study_cbcs c where c.study_id = s.id) as n,
                  (select max(created_at) from study_cbcs c where c.study_id = s.id) as last_import
           from studies s order by s.position, s.id""").fetchall()
    return jsonify([dict(r) for r in rows])


@studies_bp.route('/api/studies/<slug>')
def get_study(slug):
    db = get_db()
    study = dict(_study(db, slug))
    rows = _rows(db, study['id'])
    return jsonify({'study': study, 'rows': rows, 'stats': _stats(study['analytes'], rows),
                    'n': len(rows), 'preliminary': len(rows) < 40})


@studies_bp.route('/api/studies/parse', methods=['POST'])
def parse_payload():
    """Turn a VMACS report row or pasted text into a preview: demographics,
    every panel found, and which study it looks like it belongs to."""
    db = get_db()
    data = json_body()
    kind = text(data, 'kind')
    if kind == 'vmacs':
        header, rows = data.get('header'), data.get('rows')
        if not isinstance(header, list) or not isinstance(rows, list) or not rows:
            raise ApiError('VMACS sent no rows for this patient.')
        parsed = cbc_parse.parse_vmacs_rows([str(h) for h in header],
                                            [[str(c) for c in r] for r in rows if isinstance(r, list)])
        if not parsed['panels']:
            raise ApiError('No CBC results were found for this patient in the VMACS report format. '
                           'Check that the format has CBC_ columns and the visit is inside the search window.')
    elif kind == 'text':
        parsed = cbc_parse.parse_text(text(data, 'text'))
        if not parsed['panels']:
            raise ApiError('No results could be read from that text. One analyte per line: name, then value.')
    else:
        raise ApiError("kind must be 'vmacs' or 'text'.")

    # Which study? The breed names the species; a hint from the page wins ties.
    hint = text(data, 'study')
    studies = db.execute('select slug, species_code, species_name from studies order by position').fetchall()
    where = ' '.join(filter(None, [parsed.get('breed'), parsed.get('species')])).lower()
    match = next((s['slug'] for s in studies
                  if s['species_name'] and s['species_name'].lower().replace('-', ' ') in where.replace('-', ' ')), None)
    parsed['study_slug'] = match or (hint if any(s['slug'] == hint for s in studies) else None)
    parsed['species_mismatch'] = bool(hint and match and hint != match)
    parsed['source'] = 'vmacs' if kind == 'vmacs' else 'paste'
    return jsonify(parsed)


def _clean_results(raw):
    if not isinstance(raw, dict):
        raise ApiError('results must be an object of analyte: value.')
    results = {}
    for name, value in raw.items():
        key = cbc_parse.analyte_key(str(name))
        if not key or value is None or value == '':
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            results[key] = float(value)
        else:
            num = cbc_parse.to_number(str(value))
            results[key] = num if num is not None else str(value).strip()[:40]
    if len(results) > MAX_ANALYTES:
        raise ApiError(f'At most {MAX_ANALYTES} analytes per CBC.')
    return results


def _fields(data):
    sex = text(data, 'sex') or 'Unknown'
    if sex not in SEXES:
        raise ApiError('Sex must be Male, Female or Unknown.')
    patient = cbc_parse.digits(text(data, 'patient_no')) or None
    return {
        'patient_no': patient,
        'visit_no': cbc_parse.digits(text(data, 'visit_no')) or None,
        'wrmd_number': text(data, 'wrmd_number')[:40] or None,
        'collected_on': as_date(data, 'collected_on'),
        'age': text(data, 'age')[:40] or None,
        'sex': sex,
        'notes': text(data, 'notes')[:500] or None,
        'results': _clean_results(data.get('results') or {}),
    }


def _merge_analytes(db, study, results, offered):
    """Append analytes the study has not seen, in the order they arrive."""
    known = {a['key'] for a in study['analytes']}
    offered = {cbc_parse.analyte_key(str(a.get('key', ''))): a for a in (offered or []) if isinstance(a, dict)}
    added = list(study['analytes'])
    for key in results:
        if key in known:
            continue
        known.add(key)
        given = offered.get(key, {})
        added.append({'key': key,
                      'label': (str(given.get('label') or '').strip() or cbc_parse.analyte_label(key))[:60],
                      'unit': str(given.get('unit') or '').strip()[:20]})
    if len(added) != len(study['analytes']):
        db.execute('update studies set analytes = %s where id = %s', (Jsonb(added), study['id']))


@studies_bp.route('/api/studies/<slug>/cbcs', methods=['POST'])
def add_cbc(slug):
    db = get_db()
    study = _study(db, slug)
    data = json_body()
    f = _fields(data)
    if not any(isinstance(v, float) for v in f['results'].values()):
        raise ApiError('There are no numeric results to add.')
    source = text(data, 'source') or 'manual'
    if source not in ('vmacs', 'paste', 'manual'):
        source = 'manual'

    existing = None
    if f['patient_no']:
        existing = db.execute(
            'select id, collected_on from study_cbcs where study_id = %s and patient_no = %s',
            (study['id'], f['patient_no'])).fetchone()
    if existing and not data.get('replace'):
        # One sample per bird: a second CBC from the same patient would be
        # counted as a second animal. The person decides which one stays.
        return jsonify({
            'error': f"Patient {f['patient_no']} is already in this study"
                     + (f" (collected {existing['collected_on']})" if existing['collected_on'] else '')
                     + '. A reference interval takes one sample per bird.',
            'existing_id': existing['id'], 'duplicate': True,
        }), 409

    with write(db):
        if existing:
            row = db.execute(
                f"""update study_cbcs set visit_no = %s, wrmd_number = %s, collected_on = %s, age = %s,
                        sex = %s, source = %s, results = %s, notes = %s, added_by = %s, created_at = now()
                    where id = %s returning {_ROW}""",
                (f['visit_no'], f['wrmd_number'], f['collected_on'], f['age'], f['sex'], source,
                 Jsonb(f['results']), f['notes'], actor(), existing['id'])).fetchone()
        else:
            row = db.execute(
                f"""insert into study_cbcs (study_id, patient_no, visit_no, wrmd_number, collected_on,
                        age, sex, source, results, notes, added_by)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning {_ROW}""",
                (study['id'], f['patient_no'], f['visit_no'], f['wrmd_number'], f['collected_on'],
                 f['age'], f['sex'], source, Jsonb(f['results']), f['notes'], actor())).fetchone()
        _merge_analytes(db, study, f['results'], data.get('analytes'))
        record(db, 'study', 'study', tube_label=f['patient_no'] or 'CBC', box_label=study['name'],
               detail=('CBC replaced' if existing else 'CBC added')
                      + {'vmacs': ' from VMACS', 'paste': ' from pasted results', 'manual': ' by hand'}[source]
                      + f" · {sum(isinstance(v, float) for v in f['results'].values())} values")
    return jsonify({**dict(row), 'replaced': bool(existing)}), 201


@studies_bp.route('/api/study-cbcs/<int:cbc_id>', methods=['PUT'])
def update_cbc(cbc_id):
    db = get_db()
    current = one_or_404(db.execute(
        'select c.id, c.study_id, s.slug from study_cbcs c join studies s on s.id = c.study_id where c.id = %s',
        (cbc_id,)).fetchone(), 'CBC')
    study = _study(db, current['slug'])
    data = json_body()
    f = _fields(data)
    if f['patient_no']:
        clash = db.execute(
            'select id from study_cbcs where study_id = %s and patient_no = %s and id <> %s',
            (study['id'], f['patient_no'], cbc_id)).fetchone()
        if clash:
            raise ApiError(f"Patient {f['patient_no']} is already in this study.", 409)
    with write(db):
        row = db.execute(
            f"""update study_cbcs set patient_no = %s, visit_no = %s, wrmd_number = %s, collected_on = %s,
                    age = %s, sex = %s, results = %s, notes = %s
                where id = %s returning {_ROW}""",
            (f['patient_no'], f['visit_no'], f['wrmd_number'], f['collected_on'], f['age'], f['sex'],
             Jsonb(f['results']), f['notes'], cbc_id)).fetchone()
        _merge_analytes(db, study, f['results'], data.get('analytes'))
        record(db, 'study', 'study', tube_label=f['patient_no'] or 'CBC', box_label=study['name'],
               detail='CBC edited')
    return jsonify(dict(row))


@studies_bp.route('/api/study-cbcs/<int:cbc_id>', methods=['DELETE'])
def delete_cbc(cbc_id):
    db = get_db()
    with write(db):
        row = db.execute(
            """delete from study_cbcs c using studies s
               where c.id = %s and s.id = c.study_id returning c.patient_no, s.name""",
            (cbc_id,)).fetchone()
        if not row:
            raise ApiError('CBC not found.', 404)
        record(db, 'study', 'study', tube_label=row['patient_no'] or 'CBC', box_label=row['name'],
               detail='CBC removed from the study')
    return jsonify({'success': True})


def _display(value):
    return value if not isinstance(value, float) or value != int(value) else int(value)


@studies_bp.route('/api/studies/<slug>/xlsx')
def study_xlsx(slug):
    """The table, and only the table: values with age and sex, no statistics.
    This is the sheet that is written into the study's folder; the statistics
    belong to R."""
    db = get_db()
    study = _study(db, slug)
    rows = _rows(db, study['id'])
    wb = Workbook()
    ws = wb.active
    ws.title = 'CBC data'
    fixed = ['Patient No', 'Visit No', 'WRMD No', 'Collection Date', 'Age', 'Sex']
    headers = fixed + [a['label'] + (f" ({a['unit']})" if a.get('unit') else '') for a in study['analytes']]
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=i, value=h)
        c.font = Font(bold=True)
        c.alignment = Alignment(horizontal='center')
    for r_i, r in enumerate(rows, 2):
        base = [r['patient_no'], r['visit_no'], r['wrmd_number'], r['collected_on'], r['age'], r['sex']]
        for c_i, v in enumerate(base, 1):
            ws.cell(row=r_i, column=c_i, value=v)
        for c_i, a in enumerate(study['analytes'], len(fixed) + 1):
            v = r['results'].get(a['key'])
            if v is not None:
                ws.cell(row=r_i, column=c_i, value=_display(v))
    ws.freeze_panes = 'B2'
    for col in ws.columns:
        widest = max((len(str(cell.value or '')) for cell in col), default=8)
        ws.column_dimensions[col[0].column_letter].width = min(widest + 2, 28)
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    name = re.sub(r'[^A-Za-z0-9 _-]', '', study['name']) + ' - CBC data.xlsx'
    return send_file(out, as_attachment=True, download_name=name,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@studies_bp.route('/studies/vmacs-cbc-import.user.js')
def userscript():
    """The Tampermonkey script, with this deployment's address written in,
    so the same file works against production and against a test copy."""
    source = (Path(current_app.root_path) / 'templates' / 'vmacs-cbc-import.user.js').read_text()
    origin = request.url_root.rstrip('/')
    return Response(source.replace('__APP_ORIGIN__', origin),
                    mimetype='text/javascript',
                    headers={'Cache-Control': 'no-store'})
