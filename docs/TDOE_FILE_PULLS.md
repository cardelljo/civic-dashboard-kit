# TDOE file pulls: 901education reference

For Tennessee education workbooks, use 901education's existing
[manifest-based bundle downloader](https://github.com/cardelljo/901education/blob/main/scripts/download_tdoe_bundle.py)
and [on-demand workflow](https://github.com/cardelljo/901education/blob/main/.github/workflows/download-tdoe-files.yml).
This is a reference resource alongside the kit's API clients. Source URLs,
file lists and education-specific transformations stay in 901education.

The bundle registration is proposed in [901education PR #116](https://github.com/cardelljo/901education/pull/116);
merge it before using the new bundle on the default branch.

The [accessibility bundle](https://github.com/cardelljo/901education/tree/main/data/raw/tdoe-accessibility)
registers district growth (`2025_tvaas_district_composite.xlsx`), ACT
(`2024-25_ACT_district_suppressed.xlsx`) and college-going
(`2023_postsecondary_enrollment_suppressed.xlsx`). Its README records requested
vintages, URL verification limits, provenance and suppression requirements.

From a 901education checkout, using Python 3.9+ without extra packages:

```bash
python3 scripts/download_tdoe_bundle.py --bundle tdoe-accessibility
```

Alternatively run **Actions → Download TDOE files** there with bundle
`tdoe-accessibility`. It requests files and creates a data PR on success;
it does not run on a schedule or load the observations store.

**Access remains unverified.** Tennessee returned HTTP 403/503 to this Cloud
workspace on 2026-11-21. That reproduces the access problem already documented
in 901education, including GitHub-runner failures. Registering a bundle does
not resolve the restriction. A browser that can retrieve the files can save
them into the bundle directory, after which the same script can record them:

```bash
python3 scripts/download_tdoe_bundle.py --bundle tdoe-accessibility --record-browser-downloads
```

The downloader preserves source URL/hash provenance and reports failed files.
Automatic downloads require a release header; browser downloads record that
it is absent. Confirm workbook contents before a transformation, preserve all
suppression markers, and keep the original vintages in accessible outputs.
See the bundle README for the full operating instructions.
