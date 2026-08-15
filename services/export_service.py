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
    'Collection Date', 'Age', 'Sex', 'Freeze-Thaw Cycles',
    'WRMD Number', 'VMTH Number',
    'Shelf', 'Rack', 'Drawer', 'Box', 'Position',
    'Notes', 'Date Added',
]

RESEARCH_HEADERS = [
    'Sample ID', 'Description', 'Date Stored', 'Freeze-Thaw Cycles',
    'Shelf', 'Rack', 'Drawer', 'Box', 'Position',
    'Date Added',
]

_HEADER_FONT = Font(bold=True, color='FFFFFF', size=11)
_RAPTOR_FILL = PatternFill(start_color='0F6E78', end_color='0F6E78', fill_type='solid')
_RESEARCH_FILL = PatternFill(start_color='2F6F53', end_color='2F6F53', fill_type='solid')


def _format_position(row_pos, col_pos):
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


def _raptor_query(filters=None):
    query = """
        select rt.tube_id, s.banding_code, s.common_name, s.scientific_name,
               rt.collection_date, rt.age, rt.sex, rt.freeze_thaw_cycles,
               rt.wrmd_number, rt.vmth_number,
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
    if filters:
        if filters.get('species_id'):
            conditions.append('rt.species_id = %(species_id)s')
            params['species_id'] = filters['species_id']
        if filters.get('date_from'):
            conditions.append('rt.collection_date >= %(date_from)s')
            params['date_from'] = filters['date_from']
        if filters.get('date_to'):
            conditions.append('rt.collection_date <= %(date_to)s')
            params['date_to'] = filters['date_to']
    if conditions:
        query += ' where ' + ' and '.join(conditions)
    query += ' order by rt.tube_id'
    return query, params


def _research_query():
    return """
        select rt.sample_id, rt.description, rt.date_stored, rt.freeze_thaw_cycles,
               sh.name as shelf, r.label as rack, d.label as drawer, b.label as box,
               rt.row_pos, rt.col_pos, rt.created_at
        from research_tubes rt
        join boxes b on rt.box_id = b.id
        join drawers d on b.drawer_id = d.id
        join racks r on d.rack_id = r.id
        join shelves sh on r.shelf_id = sh.id
        order by sh.position, r.position, d.position, b.position, rt.row_pos, rt.col_pos
    """


def _raptor_row(row):
    return [
        row['tube_id'], row['banding_code'], row['common_name'], row['scientific_name'],
        row['collection_date'], row['age'], row['sex'], row['freeze_thaw_cycles'],
        row['wrmd_number'], row['vmth_number'],
        row['shelf'], row['rack'], row['drawer'], row['box'],
        _format_position(row['row_pos'], row['col_pos']),
        row['notes'], row['created_at'],
    ]


def _research_row(row):
    return [
        row['sample_id'], row['description'], row['date_stored'], row['freeze_thaw_cycles'],
        row['shelf'], row['rack'], row['drawer'], row['box'],
        _format_position(row['row_pos'], row['col_pos']),
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
    query, params = _raptor_query(filters)
    rows = db.execute(query, params).fetchall()
    return _build_workbook(
        'Raptor Plasma Biobank', RAPTOR_HEADERS, _RAPTOR_FILL, rows, _raptor_row
    )


def export_raptor_csv(db, filters=None):
    query, params = _raptor_query(filters)
    rows = db.execute(query, params).fetchall()
    return _build_csv(RAPTOR_HEADERS, rows, _raptor_row)


def export_research_xlsx(db):
    rows = db.execute(_research_query()).fetchall()
    return _build_workbook(
        'Research Samples', RESEARCH_HEADERS, _RESEARCH_FILL, rows, _research_row
    )


def export_research_csv(db):
    rows = db.execute(_research_query()).fetchall()
    return _build_csv(RESEARCH_HEADERS, rows, _research_row)
