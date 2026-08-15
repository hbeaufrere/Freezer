"""CSV and Excel export endpoints."""

import io
from datetime import date

from flask import Blueprint, request, send_file

from db import get_db
from routes.support import as_date
from services.export_service import (
    export_raptor_csv,
    export_raptor_xlsx,
    export_research_csv,
    export_research_xlsx,
)

export_bp = Blueprint('export', __name__)

XLSX_MIMETYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def _raptor_filters():
    args = request.args
    return {
        'species_id': args.get('species_id', type=int),
        'date_from': as_date(args, 'date_from'),
        'date_to': as_date(args, 'date_to'),
    }


def _stamped(name, extension):
    """Filenames carry the export date so downloads don't overwrite each other."""
    return f'{name}_{date.today().isoformat()}.{extension}'


def _csv_response(buffer, filename):
    return send_file(
        io.BytesIO(buffer.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename,
    )


@export_bp.route('/api/export/raptor/xlsx')
def raptor_xlsx():
    output = export_raptor_xlsx(get_db(), _raptor_filters())
    return send_file(
        output,
        mimetype=XLSX_MIMETYPE,
        as_attachment=True,
        download_name=_stamped('raptor_biobank', 'xlsx'),
    )


@export_bp.route('/api/export/raptor/csv')
def raptor_csv():
    output = export_raptor_csv(get_db(), _raptor_filters())
    return _csv_response(output, _stamped('raptor_biobank', 'csv'))


@export_bp.route('/api/export/research/xlsx')
def research_xlsx():
    output = export_research_xlsx(get_db())
    return send_file(
        output,
        mimetype=XLSX_MIMETYPE,
        as_attachment=True,
        download_name=_stamped('clipr_research', 'xlsx'),
    )


@export_bp.route('/api/export/research/csv')
def research_csv():
    output = export_research_csv(get_db())
    return _csv_response(output, _stamped('clipr_research', 'csv'))
