"""One pipeline container for every dashboard (docs/ARCHITECTURE.md §1.3).

Four modules, each usable on its own:

- `registry`   -- what each dashboard can run, read from that dashboard's own
                  `pipeline.json`. Standard library only, so a test that checks
                  `n8n/*.json` against it never imports a web framework.
- `migrate`    -- database migrations for one dashboard: rehearse (default),
                  apply once, record, restore. Run from the dashboard's checkout.
- `post_deploy` -- what a redeploy runs for every registered dashboard: seeds,
                  then pending migrations, then one-time jobs.
- `runner`     -- the internal HTTP dispatcher n8n calls:
                  `POST /run/{dashboard}/{job}`. Needs the `server` extra.

Everything a dashboard runs is a subprocess with the dashboard's checkout as its
working directory and the dashboard's own interpreter, so two dashboards' `scripts`
packages (and their own kit pins) never meet in one Python process. Importing this
package imports none of the four.
"""
