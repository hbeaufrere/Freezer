-- ============================================================
-- Write down which way the freezer faces.
--
-- Position 1 has always meant "nearest the front" for both drawers and boxes,
-- but that only existed as one comment on boxes.position and as an ordering in
-- the queries. Someone reading the schema had no way to tell whether B4 was at
-- the back of the drawer or the front of it, and neither did anyone reading
-- the screen.
--
-- Nothing changes structurally. This records the convention where the next
-- person will look for it, alongside the interface that now states it.
-- ============================================================

comment on column drawers.position is
    '1 = front drawer, the one that pulls out first; ascending towards the back.';

comment on column boxes.position is
    '1 = front box, nearest you when the drawer is open; ascending towards the '
    'back of the drawer.';
