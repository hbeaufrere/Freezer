-- ============================================================
-- Where the tubes and pipettes are kept at each satellite site.
--
-- The poster tells people what to do; this tells them where to find what
-- they need to do it. Per site, since each place keeps its supplies
-- somewhere different. Null means the poster says nothing about it.
-- ============================================================

alter table collection_sites add column if not exists supplies text;

comment on column collection_sites.supplies is
    'Where the Eppendorf tubes and pipettes are kept at this site, as the poster prints it.';

update collection_sites
   set supplies = 'Eppendorf tubes and pipettes are in the cabinet above the microscope in room 184.'
 where code = 'VMTH' and supplies is null;
