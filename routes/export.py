"""CSV and Excel export endpoints."""

import io
from flask import Blueprint, send_file, request
from services.export_service import (
    export_raptor_xlsx, export_raptor_csv,
    export_research_xlsx, export_research_csv,
)

export_bp = Blueprint('export', __name__)


def get_db():
    from app import get_db as _get_db
    return _get_db()


@export_bp.route('/api/export/raptor/xlsx')
def raptor_xlsx():
    filters = {
        'species_id': request.args.get('species_id', type=int),
        'date_from': request.args.get('date_from'),
        'date_to': request.args.get('date_to'),
    }
    output = export_raptor_xlsx(get_db(), filters)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='raptor_biobank_export.xlsx'
    )


@export_bp.route('/api/export/raptor/csv')
def raptor_csv():
    filters = {
        'species_id': request.args.get('species_id', type=int),
        'date_from': request.args.get('date_from'),
        'date_to': request.args.get('date_to'),
    }
    output = export_raptor_csv(get_db(), filters)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='raptor_biobank_export.csv'
    )


@export_bp.route('/api/export/research/xlsx')
def research_xlsx():
    output = export_research_xlsx(get_db())
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='research_export.xlsx'
    )


@export_bp.route('/api/export/research/csv')
def research_csv():
    output = export_research_csv(get_db())
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='research_export.csv'
    )
