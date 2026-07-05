# Project Templates

This directory contains skeleton templates for initializing new governed
projects. When a user runs `arqux init --project <name>`, the
handler creates the `.<product>/` directory using these templates as a
starting point.

## Files

- `manifest.cortex.tmpl` — workspace manifest template
- `brain.cortex.tmpl` — project brain template
- `meta-brain.cortex.tmpl` — workspace meta-brain template

Each template uses `{{var}}` placeholders that the handler substitutes
at creation time. The variables available are:

- `{{product}}` — lowercase product name
- `{{product_upper}}` — uppercase product name
- `{{product_title}}` — title-case product name
- `{{project}}` — chosen project name
- `{{path}}` — absolute path to the project
- `{{timestamp}}` — ISO-8601 creation timestamp

After substitution, the handler writes both `.cortex` (machine) and
`.md` (human) forms, keeping them in sync via the `cortex` CLI.
