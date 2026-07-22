# camplang.org

Future Camp website source.

## Layout

- `content/` contains handwritten website content such as the home page,
  install page, and non-reference pages.
- `docs/` is reserved for website-facing documentation notes that are not
  generated reference content.
- `planning/` contains website planning and brand reference documents.
- `public/` is generated static output. It is ignored; CI should build and
  publish it.
- `tool/` contains the static-site build tooling, templates, styles, static
  assets, and ignored staging input.

The initial website is implemented with the Zola-based static-site build
described in `planning/CAMPLANG_ORG_WEBSITE_PLAN.md`.
