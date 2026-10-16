-- ============================================================
-- Where the satellite freezer actually is, in words a poster can print.
--
-- The seed said "Ordinary freezer, VMTH", which locates nothing. The
-- drop-off poster tells people where to put the tubes, so the location
-- has to be a place. Only the seed wording is replaced; anything someone
-- has since edited is left alone.
-- ============================================================

update collection_sites
   set location = 'the freezer in room 181, VMTH'
 where code = 'VMTH' and location = 'Ordinary freezer, VMTH';

update collection_sites
   set location = 'the sample freezer at the CRC'
 where code = 'CRC' and location = 'Ordinary freezer, CRC';
