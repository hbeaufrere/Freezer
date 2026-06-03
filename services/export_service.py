"""Excel and CSV export generation for raptor and research data."""

import csv
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment


def _raptor_query(filters=None):
    query = """
        SELECT rt.tube_id, s.banding_code, s.common_name, s.scientific_name,
               rt.collection_date, rt.age, rt.sex, rt.freeze_thaw_cycles,
               rt.wrmd_number, rt.vmth_number,
               sh.name AS shelf, r.label AS rack, d.label AS drawer, b.label AS box,
               rt.row_pos, rt.col_pos,
               rt.notes, rt.created_at
        FROM raptor_tubes rt
        JOIN species s ON rt.species_id = s.id
        JOIN boxes b ON rt.box_id = b.id
        JOIN drawers d ON b.drawer_id = d.id
        JOIN racks r ON d.rack_id = r.id
        JOIN shelves sh ON r.shelf_id = sh.id
    """
    params = []
    conditions = []
    if filters:
        if filters.get('species_id'):
            conditions.append("rt.species_id = %s")
            params.append(filters['species_id'])
        if filters.get('date_from'):
            conditions.append("rt.collection_date >= %s")
            params.append(filters['date_from'])
        if filters.get('date_to'):
            conditions.append("rt.collection_date <= %s")
            params.append(filters['date_to'])
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY rt.tube_id"
    return query, params


RAPTOR_HEADERS = [
    "Tube ID", "Species Code", "Common Name", "Scientific Name",
    "Collection Date", "Age", "Sex", "Freeze-Thaw Cycles",
    "WRMD Number", "VMTH Number",
    "Shelf", "Rack", "Drawer", "Box", "Position",
    "Notes", "Date Added"
]

RESEARCH_HEADERS = [
    "Sample ID", "Description", "Date Stored", "Freeze-Thaw Cycles",
    "Shelf", "Rack", "Drawer", "Box", "Position",
    "Date Added"
]


_ROW_LABELS = ['A','B','C','D','E','F','G','H','J','K']

def _format_position(row_pos, col_pos):
    """Convert 1-based row/col to label like A1, B3. Skips I (row 9 = J)."""
    letter = _ROW_LABELS[row_pos - 1] if row_pos <= len(_ROW_LABELS) else chr(64 + row_pos)
    return f"{letter}{col_pos}"


_RAPTOR_KEYS = [
    'tube_id', 'banding_code', 'common_name', 'scientific_name',
    'collection_date', 'age', 'sex', 'freeze_thaw_cycles',
    'wrmd_number', 'vmth_number',
    'shelf', 'rack', 'drawer', 'box',
    'row_pos', 'col_pos',
    'notes', 'created_at',
]


def _raptor_row(row):
    """Format a raptor query result row for export."""
    return [
        row['tube_id'],
        row['banding_code'],
        row['common_name'],
        row['scientific_name'],
        row['collection_date'],
        row['age'],
        row['sex'],
        row['freeze_thaw_cycles'],
        row['wrmd_number'],
        row['vmth_number'],
        row['shelf'],
        row['rack'],
        row['drawer'],
        row['box'],
        _format_position(row['row_pos'], row['col_pos']),
        row['notes'],
        row['created_at'],
    ]


def export_raptor_xlsx(db, filters=None):
    query, params = _raptor_query(filters)
    rows = db.execute(query, params).fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "Raptor Plasma Biobank"

    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")

    for col_idx, header in enumerate(RAPTOR_HEADERS, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')

    for row_idx, row in enumerate(rows, 2):
        for col_idx, value in enumerate(_raptor_row(row), 1):
            ws.cell(row=row_idx, column=col_idx, value=_xlsx_value(value))

    for col in ws.columns:
        max_length = max((len(str(cell.value or "")) for cell in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_length + 2, 30)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def export_raptor_csv(db, filters=None):
    query, params = _raptor_query(filters)
    rows = db.execute(query, params).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(RAPTOR_HEADERS)
    for row in rows:
        writer.writerow([_csv_value(v) for v in _raptor_row(row)])
    output.seek(0)
    return output


def _research_query():
    return """
        SELECT rt.sample_id, rt.description, rt.date_stored, rt.freeze_thaw_cycles,
               sh.name AS shelf, r.label AS rack, d.label AS drawer, b.label AS box,
               rt.row_pos, rt.col_pos,
               rt.created_at
        FROM research_tubes rt
        JOIN boxes b ON rt.box_id = b.id
        JOIN drawers d ON b.drawer_id = d.id
        JOIN racks r ON d.rack_id = r.id
        JOIN shelves sh ON r.shelf_id = sh.id
        ORDER BY sh.position, r.position, d.position, b.position, rt.row_pos, rt.col_pos
    """


def _research_row(row):
    return [
        row['sample_id'],
        row['description'],
        row['date_stored'],
        row['freeze_thaw_cycles'],
        row['shelf'],
        row['rack'],
        row['drawer'],
        row['box'],
        _format_position(row['row_pos'], row['col_pos']),
        row['created_at'],
    ]


def export_research_xlsx(db):
    rows = db.execute(_research_query()).fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "Research Samples"

    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="059669", end_color="059669", fill_type="solid")

    for col_idx, header in enumerate(RESEARCH_HEADERS, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')

    for row_idx, row in enumerate(rows, 2):
        for col_idx, value in enumerate(_research_row(row), 1):
            ws.cell(row=row_idx, column=col_idx, value=_xlsx_value(value))

    for col in ws.columns:
        max_length = max((len(str(cell.value or "")) for cell in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_length + 2, 30)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def export_research_csv(db):
    rows = db.execute(_research_query()).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(RESEARCH_HEADERS)
    for row in rows:
        writer.writerow([_csv_value(v) for v in _research_row(row)])
    output.seek(0)
    return output


def _xlsx_value(v):
    # openpyxl handles native datetime/date — strip tz if needed
    if hasattr(v, 'replace') and hasattr(v, 'tzinfo') and v.tzinfo is not None:
        return v.replace(tzinfo=None)
    return v


def _csv_value(v):
    if v is None:
        return ''
    return str(v)
