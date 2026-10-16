"""The raptor biobank as a map: structure only, nothing about contents."""

import re
from collections import defaultdict
from datetime import date

_CODE = re.compile(r'\b[A-Z]{4}\b')


def raptor_map(db):
    shelves = db.execute(
        "select id, name, position from shelves where section = 'raptor' order by position"
    ).fetchall()
    ids = [s['id'] for s in shelves]
    racks = db.execute(
        'select id, shelf_id, position, label, designation from racks '
        'where shelf_id = any(%s) order by shelf_id, position', (ids,)
    ).fetchall()
    rack_ids = [r['id'] for r in racks]
    drawers = db.execute(
        'select id, rack_id, position, label, note from drawers '
        'where rack_id = any(%s) order by rack_id, position', (rack_ids,)
    ).fetchall()
    boxes = db.execute(
        """select b.id, b.drawer_id, b.position, b.label, b.grid_rows, b.grid_cols
           from boxes b join drawers d on b.drawer_id = d.id
           where d.rack_id = any(%s) order by b.drawer_id, b.position""", (rack_ids,)
    ).fetchall()
    species = {
        s['banding_code']: s for s in db.execute(
            'select banding_code, common_name, scientific_name from species').fetchall()
    }

    by_drawer = defaultdict(list)
    for b in boxes:
        by_drawer[b['drawer_id']].append(dict(b))
    by_rack = defaultdict(list)
    for d in drawers:
        entry = dict(d)
        entry['boxes'] = by_drawer.get(d['id'], [])
        by_rack[d['rack_id']].append(entry)

    # The species lines name banding codes; the legend spells them out, in the
    # order they first appear across the racks, so the two read together.
    legend, seen = [], set()
    by_shelf = defaultdict(list)
    for r in racks:
        entry = dict(r)
        entry['drawers'] = by_rack.get(r['id'], [])
        entry['codes'] = []
        for code in _CODE.findall(r['designation'] or ''):
            if code in species:
                entry['codes'].append(code)
                if code not in seen:
                    seen.add(code)
                    legend.append({'code': code, 'name': species[code]['common_name'],
                                   'scientific': species[code]['scientific_name']})
        by_shelf[r['shelf_id']].append(entry)

    out = []
    for sh in shelves:
        entry = dict(sh)
        entry['racks'] = by_shelf.get(sh['id'], [])
        out.append(entry)

    widest = max((len(d['boxes']) for r in racks for d in by_rack.get(r['id'], [])), default=4)
    deepest = max((len(by_rack.get(r['id'], [])) for r in racks), default=8)
    return {'shelves': out, 'legend': legend, 'box_columns': widest,
            'drawer_rows': deepest, 'printed_on': date.today().isoformat()}
