# TDOE file pulls: 901education reference

For Tennessee education workbooks, use 901education's existing code. Source URLs,
file lists and education-specific transformations stay in 901education; this page
is a reference alongside the kit's API clients.

## The route

www.tn.gov refuses scripted downloads (403). The state's kidcentral content host,
`www.kidcentraltn.extglb.tn.gov`, serves the same `/content/dam/tn/education/` paths.
Cardell reported on 2026-11-21 that, from checking with TDOE, it is an acceptable
alternative. Keep the www.tn.gov address as the recorded source.

- **Scheduled jobs:** 901education's `scripts/tdoe_utils.download`, used by every
  `fetch_tdoe_*` job, tries the content host first and then www.tn.gov.
  `TDOE_MIRROR=0` turns it off.
- **File bundles:** the
  [bundle downloader](https://github.com/cardelljo/901education/blob/main/scripts/download_tdoe_bundle.py)
  and [on-demand workflow](https://github.com/cardelljo/901education/blob/main/.github/workflows/download-tdoe-files.yml).
  From a 901education checkout, with Python 3.9+ and no extra packages:

```bash
python3 scripts/download_tdoe_bundle.py --bundle tdoe-nashville --mirror
```

The manifest keeps the www.tn.gov `url`, records the host used as `requestUrl`, and
stores Last-Modified and SHA-256. Workbooks must pass ZIP and workbook XML checks. A
download dated earlier than the saved release is refused, because the content host can
hold an older copy; compare a refresh with TDOE's download page too.

The 2024-25 district growth, 2024-25 ACT and 2023 college-going workbooks are in
[`data/raw/tdoe-nashville`](https://github.com/cardelljo/901education/tree/main/data/raw/tdoe-nashville).

## Fallback

If neither host works, save the files from a browser into the bundle folder and record them:

```bash
python3 scripts/download_tdoe_bundle.py --bundle tdoe-nashville --record-browser-downloads
```

Browser entries have no release date, so date them by the data year, never by the download.

## Not yet tested

The content host answered from a cloud workspace. Runs from 901education's pipeline
server and GitHub's runners are untested.

Preserve published suppression markers and the original vintages in any output built
from these files.
