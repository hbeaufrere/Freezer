-- ============================================================
-- Write down how the freezer is laid out.
--
-- The two levels count along different axes, which is exactly why it needed
-- writing down: drawers stack vertically (D1 at the top) while the boxes
-- inside a drawer sit one behind another (B1 at the front). Position 1 means
-- "first", and "first" is downwards in one case and towards you in the other.
--
-- Only boxes.position carried a comment before, and neither fact reached the
-- screen. Nothing changes structurally here; this records the convention where
-- the next person will look for it, alongside the interface that now states it.
-- ============================================================

comment on column drawers.position is
    '1 = top drawer; ascending downwards through the rack.';

comment on column boxes.position is
    '1 = front box, nearest you when the drawer is open; ascending towards the '
    'back of the drawer.';
