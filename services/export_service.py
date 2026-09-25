"""Excel and CSV export generation for raptor and research data."""

import csv
import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

# Row letters skip I, which is too easily read as 1 on a frozen label.
_ROW_LABELS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K']

RAPTOR_HEADERS = [
    'Tube ID', 'Species Code', 'Common Name', 'Scientific Name',
    'Sample Type', 'Blood Timing', 'Anticoagulant',
    'Collection Date', 'Age', 'Sex', 'Freeze-Thaw Cycles',
    'WRMD Number', 'VMACS Number',
    'Shelf', 'Rack', 'Drawer', 'Box', 'Position',
    'Notes', 'Date Added',
]

RESEARCH_HEADERS = [
    'Sample ID', 'Description', 'Tubes', 'Date Stored', 'Freeze-Thaw Cycles',
    'Shelf', 'Rack', 'Drawer', 'Box', 'Position',
    'Date Added',
]

_HEADER_FONT = Font(bold=True, color='FFFFFF', size=11)
_RAPTOR_FILL = PatternFill(start_color='022851', end_color='022851', fill_type='solid')
_RESEARCH_FILL = PatternFill(start_color='0A3D75', end_color='0A3D75', fill_type='solid')


def format_position(row_pos, col_pos):
    """Turn 1-based row/column into a grid label such as A1 or J10."""
    if row_pos is None or col_pos is None:
        return ''
    letter = _ROW_LABELS[row_pos - 1] if row_pos <= len(_ROW_LABELS) else chr(64 + row_pos)
    return f'{letter}{col_pos}'


def _excel_safe(value):
    """Excel cannot store timezone-aware datetimes, so hand it naive UTC."""
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value


# Every criterion the biobank can be sliced by, and the SQL each one adds.
# Kept in one table so the on-screen list, the CSV and the workbook cannot
# drift apart — a count you can see but not download is worse than no count.
_RAPTOR_CRITERIA = {
    'species_id': 'rt.species_id = %(species_id)s',
    'sample_type': 'rt.sample_type = %(sample_type)s',
    'blood_timing': 'rt.blood_timing = %(blood_timing)s',
    'anticoagulant': 'rt.anticoagulant = %(anticoagulant)s',
    'sex': 'rt.sex = %(sex)s',
    'age': 'rt.age = %(age)s',
    'date_from': 'rt.collection_date >= %(date_from)s',
    'date_to': 'rt.collection_date <= %(date_to)s',
}


def raptor_query(filters=None):
    query = """
        select rt.tube_id, s.banding_code, s.common_name, s.scientific_name,
               rt.sample_type, rt.blood_timing, rt.anticoagulant,
               rt.collection_date, rt.age, rt.sex,
               rt.freeze_thaw_cycles, rt.wrmd_number, rt.vmth_number,
               sh.name as shelf, r.label as rack, d.label as drawer, b.label as box,
               rt.row_pos, rt.col_pos, rt.notes, rt.created_at
        from raptor_tubes rt
        join species s on rt.species_id = s.id
        join boxes b on rt.box_id = b.id
        join drawers d on b.drawer_id = d.id
        join racks r on d.rack_id = r.id
        join shelves sh on r.shelf_id = sh.id
    """
    conditions, params = [], {}
    for field, clause in _RAPTOR_CRITERIA.items():
        value = (filters or {}).get(field)
        # A blank select means "any", not "match the empty string".
        if value is None or value == '':
            continue
        conditions.append(clause)
        params[field] = value
    if conditions:
        query += ' where ' + ' and '.join(conditions)
    query += ' order by rt.tube_id'
    return query, params


# The research criteria, mirrored from the raptor ones: one predicate for
# the on-screen list, the CSV and the workbook, so they cannot disagree.
# ``q`` is the one people actually type — a sample ID or a word from the
# description — and for a whole box it matches the study and sample type.
_RESEARCH_TUBE_CRITERIA = {
    'q': '(rt.sample_id ilike %(q)s or rt.description ilike %(q)s)',
    'rack_id': 'r.id = %(rack_id)s',
    'date_from': 'rt.date_stored >= %(date_from)s',
    'date_to': 'rt.date_stored <= %(date_to)s',
}
_RESEARCH_BOX_CRITERIA = {
    'q': '(b.bulk_study ilike %(q)s or b.bulk_sample_type ilike %(q)s or b.label ilike %(q)s)',
    'rack_id': 'r.id = %(rack_id)s',
    # A whole box has no date, so a date range excludes it outright rather
    # than passing it through as if it matched.
    'date_from': 'false',
    'date_to': 'false',
}


def research_query(filters=None):
    """Itemised tubes, then whole boxes as one row each with their count.

    A whole box's tubes were never labelled individually, so a row per tube
    would be a fiction; one row saying "48 tubes, plasma, Kestrel PK" is the
    truth the freezer holds.
    """
    filters = filters or {}
    params = {}
    tube_where, box_where = [], []
    for field, value in filters.items():
        if value is None or value == '':
            continue
        if field == 'q':
            params['q'] = f'%{value}%'
        else:
            params[field] = value
        tube_where.append(_RESEARCH_TUBE_CRITERIA[field])
        box_where.append(_RESEARCH_BOX_CRITERIA[field])

    tube_clause = (' where ' + ' and '.join(tube_where)) if tube_where else ''
    box_clause = ' and ' + ' and '.join(box_where) if box_where else ''

    query = f"""
        select rt.id, rt.box_id, rt.sample_id, rt.description, 1 as tubes,
               rt.date_stored, rt.freeze_thaw_cycles,
               sh.name as shelf, r.label as rack, d.label as drawer, b.label as box,
               rt.row_pos, rt.col_pos, rt.created_at,
               sh.position as sp, r.position as rp, d.position as dp, b.position as bp
        from research_tubes rt
        join boxes b on rt.box_id = b.id
        join drawers d on b.drawer_id = d.id
        join racks r on d.rack_id = r.id
        join shelves sh on r.shelf_id = sh.id
        {tube_clause}
        union all
        select null as id, b.id as box_id, null as sample_id,
               concat_ws(' — ', b.bulk_sample_type, b.bulk_study) as description,
               coalesce(b.bulk_tube_count, 0) as tubes,
               null as date_stored, null as freeze_thaw_cycles,
               sh.name, r.label, d.label, b.label,
               null, null, null,
               sh.position, r.position, d.position, b.position
        from boxes b
        join drawers d on b.drawer_id = d.id
        join racks r on d.rack_id = r.id
        join shelves sh on r.shelf_id = sh.id
        where b.box_type = 'bulk'{box_clause}
        order by sp, rp, dp, bp, row_pos, col_pos
    """
    return query, params


def _raptor_row(row):
    return [
        row['tube_id'], row['banding_code'], row['common_name'], row['scientific_name'],
        row['sample_type'], row['blood_timing'], row['anticoagulant'],
        row['collection_date'], row['age'], row['sex'],
        row['freeze_thaw_cycles'],
        row['wrmd_number'], row['vmth_number'],
        row['shelf'], row['rack'], row['drawer'], row['box'],
        format_position(row['row_pos'], row['col_pos']),
        row['notes'], row['created_at'],
    ]


def _research_row(row):
    return [
        row['sample_id'] or '(whole box)', row['description'], row['tubes'],
        row['date_stored'], row['freeze_thaw_cycles'],
        row['shelf'], row['rack'], row['drawer'], row['box'],
        format_position(row['row_pos'], row['col_pos']),
        row['created_at'],
    ]


def _build_workbook(title, headers, fill, rows, to_values):
    wb = Workbook()
    ws = wb.active
    ws.title = title

    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = _HEADER_FONT
        cell.fill = fill
        cell.alignment = Alignment(horizontal='center')

    for row_idx, row in enumerate(rows, 2):
        for col_idx, value in enumerate(to_values(row), 1):
            ws.cell(row=row_idx, column=col_idx, value=_excel_safe(value))

    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions

    for col in ws.columns:
        widest = max((len(str(cell.value or '')) for cell in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(widest + 2, 30)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def _build_csv(headers, rows, to_values):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(to_values(row))
    output.seek(0)
    return output


def export_raptor_xlsx(db, filters=None):
    query, params = raptor_query(filters)
    rows = db.execute(query, params).fetchall()
    return _build_workbook(
        'Raptor Biobank', RAPTOR_HEADERS, _RAPTOR_FILL, rows, _raptor_row
    )


def export_raptor_csv(db, filters=None):
    query, params = raptor_query(filters)
    rows = db.execute(query, params).fetchall()
    return _build_csv(RAPTOR_HEADERS, rows, _raptor_row)


def export_research_xlsx(db, filters=None):
    query, params = research_query(filters)
    rows = db.execute(query, params).fetchall()
    return _build_workbook(
        'Research Samples', RESEARCH_HEADERS, _RESEARCH_FILL, rows, _research_row
    )


def export_research_csv(db, filters=None):
    query, params = research_query(filters)
    rows = db.execute(query, params).fetchall()
    return _build_csv(RESEARCH_HEADERS, rows, _research_row)
