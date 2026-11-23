# Germplasm Evidence Layout

Use this layout for local cultivar and germplasm candidates:

```text
templates/
  germplasm_specimen_template.md
records/
  <sample-id>.md
evidence/
  photos/<sample-id>/          sanitized images only
  lab/<sample-id>/             sanitized signed reports only
data/
  derived/<sample-id>/         compact derived tables and summaries
manifests/
  <sample-id>.json             hashes, provenance and external accessions
```

## Keep Outside Git

- FASTQ, BAM, CRAM, raw metagenomic or whole-genome data;
- exact private/home coordinates and addresses;
- unsanitized certificates, contracts, receipts and personal identifiers;
- quarantine-sensitive pathogen handling records;
- credentials or private laboratory portals.

Large raw data should use an appropriate controlled institutional store or a
recognized sequence archive when release is lawful. Git stores only checksums,
accession identifiers, derived summaries, and public-safe evidence.

## Versioning Rules

1. The biological sample ID never changes.
2. Every sucker, tissue-culture passage, or destructive subsample gets a child ID.
3. Records are append-only; corrections retain the prior statement and reason.
4. Every derived result names its sample, passage, method, software, parameters,
   reference accessions, and source-data checksum.
5. Commercial claims, operator observations, laboratory measurements, and
   peer-reviewed conclusions remain separate evidence classes.

## Safety Gate

No repository record authorizes pathogen acquisition, transport, culture, or
challenge work. Foc TR4 work requires national phytosanitary approval and an
authorised plant-quarantine containment facility. FAO guidance is a reference;
FAO is not represented here as an authority that certifies individual laboratories.
