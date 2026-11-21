# TDOE file pulls: 901education reference

For Tennessee education workbooks, use 901education's existing
[manifest-based bundle downloader](https://github.com/cardelljo/901education/blob/main/scripts/download_tdoe_bundle.py)
and [on-demand workflow](https://github.com/cardelljo/901education/blob/main/.github/workflows/download-tdoe-files.yml).
This is a reference resource alongside the kit's API clients. Source URLs,
file lists and education-specific transformations stay in 901education.

The [accessibility bundle](https://github.com/cardelljo/901education/tree/main/data/raw/tdoe-accessibility)
registers district growth (`2025_tvaas_district_composite.xlsx`), ACT
(`2024-25_ACT_district_suppressed.xlsx`) and college-going
(`2023_postsecondary_enrollment_suppressed.xlsx`). Its README records requested
vintages, URL verification limits, provenance and suppression requirements.

From a 901education checkout, using Python 3.9+ without extra packages:

```bash
python3 scripts/download_tdoe_bundle.py --bundle tdoe-accessibility --mirror
```

Alternatively run **Actions → Download TDOE files** there with bundle
`tdoe-accessibility`. It requests files and creates a data PR on success;
it does not run on a schedule or load the observations store.

**Mirror downloads verified, 2026-11-21.** All three requested workbooks downloaded
from the indexed public Tennessee host `www.kidcentraltn.extglb.tn.gov` using the
explicit `--mirror` option. Original files and a manifest are included in the
companion PR. The manifest retains canonical source URLs, records the actual
mirror request URLs, Last-Modified headers and SHA-256 hashes. ZIP integrity and
workbook XML checks passed. The workflow's mirror input defaults on.

The normal `www.tn.gov` route still returned 403/503. The mirror is cached;
compare releases against the official download page before updating. This is
verified from Cloud, not yet from GitHub runners or the Coolify server. If both
routes fail, save files from an accessible browser and record them:

```bash
python3 scripts/download_tdoe_bundle.py --bundle tdoe-accessibility --record-browser-downloads
```

The downloader preserves source URL/hash provenance and reports failed files.
Automatic downloads require a release header; browser downloads record that
it is absent. Confirm workbook contents before a transformation, preserve all
suppression markers, and keep the original vintages in accessible outputs.
See the bundle README for the full operating instructions.

