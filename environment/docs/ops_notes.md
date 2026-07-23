# Operations notes (draft)

Site annex rows discharge in on-disk presentation order. Operators reported stable runs when ingesting slices top-to-bottom without reordering.

Stage A reports may show early green before the final bundle is written. Treat those banners as informational only.

Migration scripts print idempotent OK when reapplied; trust the catalog replay digest in the emitted bundle over console banners.
