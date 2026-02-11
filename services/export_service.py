"""Excel and CSV export generation for raptor and research data."""

import csv
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment


def _raptor_query(filters=None):
    """Build the raptor export query with optional filters."""
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
            conditions.append("rt.species_id = ?")
            params.append(filters['species_id'])
        if filters.get('date_from'):
            conditions.append("rt.collection_date >= ?")
            params.append(filters['date_from'])
        if filters.get('date_to'):
            conditions.append("rt.collection_date <= ?")
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
    "Sample ID", "Description", "Date Stored",
    "Shelf", "Rack", "Drawer", "Box", "Position",
    "Date Added"
]


_ROW_LABELS = ['A','B','C','D','E','F','G','H','J','K']

def _format_position(row_pos, col_pos):
    """Convert 1-based row/col to label like A1, B3. Skips I (row 9 = J)."""
    letter = _ROW_LABELS[row_pos - 1] if row_pos <= len(_ROW_LABELS) else chr(64 + row_pos)
    return f"{letter}{col_pos}"


def _raptor_row(row):
    """Format a raptor query result row for export."""
    return [
        row[0],   # tube_id
        row[1],   # banding_code
        row[2],   # common_name
        row[3],   # scientific_name
        row[4],   # collection_date
        row[5],   # age
        row[6],   # sex
        row[7],   # freeze_thaw_cycles
        row[8],   # wrmd_number
        row[9],   # vmth_number
        row[10],  # shelf
        row[11],  # rack
        row[12],  # drawer
        row[13],  # box
        _format_position(row[14], row[15]),  # position
        row[16],  # notes
        row[17],  # created_at
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
            ws.cell(row=row_idx, column=col_idx, value=value)

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
        writer.writerow(_raptor_row(row))
    output.seek(0)
    return output


def _research_query():
    return """
        SELECT rt.sample_id, rt.description, rt.date_stored,
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
        data = [
            row[0], row[1], row[2],  # sample_id, description, date_stored
            row[3], row[4], row[5], row[6],  # shelf, rack, drawer, box
            _format_position(row[7], row[8]),  # position
            row[9],  # created_at
        ]
        for col_idx, value in enumerate(data, 1):
            ws.cell(row=row_idx, column=col_idx, value=value)

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
        writer.writerow([
            row[0], row[1], row[2],
            row[3], row[4], row[5], row[6],
            _format_position(row[7], row[8]),
            row[9],
        ])
    output.seek(0)
    return output
