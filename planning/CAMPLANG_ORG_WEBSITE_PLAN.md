# Camp Website Sketch

## Summary

The Camp website should be a static site generated from three sources:

- handwritten website content in `camplang.org/content`;
- the compiler repo documentation in `dev/docs`, especially the language guide;
- generated API documentation from Camp metadata for the standard library and sponsored extension packages.

My recommendation is to build this with **Zola** unless you strongly prefer the larger Hugo ecosystem. Zola is a fast static site generator written in Rust, uses CommonMark markdown, uses Tera templates, includes Sass and syntax highlighting, and produces plain static files. It fits the constraints well: established enough, fast, typed implementation, little or no browser JavaScript, and simple local builds.

Official references:

- Zola: https://www.getzola.org/
- Hugo: https://gohugo.io/
- MkDocs: https://www.mkdocs.org/
- Material for MkDocs: https://squidfunk.github.io/mkdocs-material/
- Astro: https://astro.build/

## Recommended Shape

Use `camplang.org` as the website repo, with this layout:

```text
camplang.org/
	content/
		_index.md
		install.md
		features.md
		community.md
	public/
		[generated static site committed or deployed]
	tool/
		build.sh
		config.toml
		templates/
		sass/
		static/
		staging/
			[generated working input, ignored]
```

The important split is:

- `content/` is the human-authored non-doc content.
- `tool/` owns templates, CSS, build scripts, and staging.
- `public/` is the generated static output for GitHub Pages or another static host.

I would make `tool/staging/` ignored. The build script can assemble a full Zola input tree there, then tell Zola to emit `../public`.

That keeps `content/` pleasant to edit and prevents generated copies of `dev/docs` from becoming a second source of truth.

## Why Zola

Zola is the best match for the stated preferences:

- It is written in Rust and ships as a single binary.
- It builds quickly.
- It uses CommonMark markdown.
- Templates use Tera, which is typed-language-friendly in spirit and closer to Jinja/Django style than ad hoc JavaScript rendering.
- It can produce a static, mostly HTML/CSS site with no required client-side framework.
- Built-in Sass and syntax highlighting are useful for docs without adding a JavaScript toolchain.

The tradeoff is ecosystem size. Hugo has more themes and more examples. If the project wants maximum theme availability and long-term familiarity for contributors, Hugo is the conservative choice. If the project wants a smaller, cleaner, fast tool with fewer moving parts, Zola is the better fit.

## Other Options

### Hugo

Hugo is the most conservative static-site-generator choice. It is fast, mature, and has a large theme ecosystem. It is written in Go and is broadly used for project sites and documentation.

I would choose Hugo if:

- the top priority is theme availability;
- we want the largest pool of examples and prior art;
- we expect non-Camp contributors to already know the tool.

The main downside is that Hugo configuration and templating can become its own language. It is powerful, but it can be more intricate than this site needs.

### MkDocs With Material

MkDocs is excellent for documentation. Material for MkDocs is polished, responsive, searchable, and very productive.

I would choose MkDocs only if the website is primarily documentation and the landing page is secondary. It is less ideal for a language homepage because its structure wants to be a docs portal first. It also uses Python, which is fine, but it is not as aligned with the “typed and lightweight” preference.

### Astro

Astro can generate very fast static sites and can ship very little JavaScript when used carefully. It is excellent for content-heavy sites that still need rich components.

I would not start with Astro here. It is a JavaScript/TypeScript ecosystem tool. TypeScript is typed, but the surrounding dependency chain is still npm-based and heavier than we need for a language documentation site.

## Site Structure

The generated site should look like this:

```text
/
	Home
/install/
	Install instructions and platform notes
/docs/
	Language guide
/docs/compiler/
	Compiler guide
/docs/stdlib/
	Generated standard library API
/docs/packages/ext-json/
	Generated ext-json API
/docs/packages/[package]/
	Generated package API
/github/
	Redirect or ordinary link to compiler GitHub page
```

The home page should be a landing page, but not a marketing maze. It should quickly answer:

- What is Camp?
- What does Camp optimize for?
- What does a tiny Camp program look like?
- How do I install it?
- Where are the docs?
- Where is the compiler source?

For installation, we can show intended commands with clear “planned” wording until package managers are real:

```sh
brew install camplang/tap/camp
choco install camp
winget install CampLang.Camp
```

Until those exist, the page should also include a working “build from source” path.

## Visual Direction

The site should feel like a language/tooling site, not a SaaS product page.

I would use:

- a restrained first viewport with a real code sample and direct install/docs links;
- a compact feature grid below the first fold;
- clear typography, good line length, and strong code block styling;
- responsive navigation that works without JavaScript, using plain links and CSS;
- optional progressive enhancement for search, but no dependency on it for navigation.

The docs area should prioritize reading:

- left-side navigation on desktop;
- top or collapsible section navigation on mobile;
- previous/next links at the bottom of guide pages;
- stable heading anchors;
- syntax-highlighted Camp code blocks;
- no heavy client-side app shell.

## Build Flow

The build script should do roughly this:

```sh
cd ~/Projects/camplang/camplang.org

tool/build.sh
```

Internally:

1. Remove and recreate `tool/staging`.
2. Copy `content/` into `tool/staging/content`.
3. Copy selected docs from `../dev/docs/language` into `tool/staging/content/docs/language`.
4. Copy selected compiler docs from `../dev/docs/compiler` into `tool/staging/content/docs/compiler`.
5. Run `../dev/bin/campc dump metadata` or a purpose-built API-doc command for stdlib and packages.
6. Convert metadata JSON into markdown pages under `tool/staging/content/docs/stdlib` and `tool/staging/content/docs/packages/...`.
7. Run Zola with `tool/config.toml`, `tool/templates`, `tool/sass`, and `tool/staging/content`.
8. Emit static files into `public/`.

The build can start simpler:

- phase 1: landing page plus copied language guide;
- phase 2: compiler docs and navigation polish;
- phase 3: generated standard library API docs;
- phase 4: generated package API docs.

## Synchronizing With Code

The source of truth should remain where each kind of content naturally lives:

- language guide: `dev/docs/language`;
- compiler docs: `dev/docs/compiler`;
- stdlib API: generated from the current compiler/stdlib metadata;
- sponsored package API: generated from package source metadata;
- website landing/install pages: `camplang.org/content`.

The website should not manually edit copies of the language guide or API docs.
Generated pages should be reproducible from the current local repos.

For day-to-day sync, add a script such as:

```sh
camplang.org/tool/build.sh
```

For release sync, add a stricter script such as:

```sh
camplang.org/tool/build-release.sh --camp-version 0.1.0
```

The release build should:

- build the compiler from `dev`;
- generate stdlib metadata with that compiler;
- generate package metadata from `pkg.camplang.org`;
- stamp the website with the Camp version and commit hashes;
- fail if generated output changes unexpectedly in CI.

## Day-To-Day Use

For ordinary website edits:

```sh
cd ~/Projects/camplang/camplang.org
$EDITOR content/_index.md
tool/serve.sh
```

`tool/serve.sh` would run Zola’s local server against the staging tree and rebuild when content changes. Editing the landing page stays fast and isolated from compiler development.

For documentation edits:

```sh
cd ~/Projects/camplang/dev
$EDITOR docs/language/06-functions-methods-and-callables.md
cd ../camplang.org
tool/build.sh
```

The website build imports the current docs. There is no copy/paste step.

For API docs:

```sh
cd ~/Projects/camplang/camplang.org
tool/build.sh --api
```

The API generator should consume metadata JSON and produce deterministic markdown. That generated markdown lives in staging, not as hand-maintained source.

## API Documentation Generator

The API documentation generator should probably be a small typed tool rather than template logic.

Good candidates:

- a C# console tool in `camplang.org/tool/api-docs`;
- a Rust tool if the site uses Zola and we want a Rust-only website toolchain;
- eventually, a Camp tool once Camp is self-hosting enough for this kind of utility.

I would start with C# because the compiler and metadata model are already in C#. It can read metadata JSON, group declarations by namespace/type, and emit markdown that the static-site generator consumes.

Generated API pages should include:

- namespace/type/function pages;
- declaration signatures;
- doc comments from metadata;
- parameter docs;
- visibility/export status;
- source package/module name;
- links from type references to their API pages when possible.

The API generator should treat metadata as the contract. It should not scrape `.camp` files.

## GitHub Pages And Domain

For GitHub Pages with `camplang.org`, the repo can serve static files from:

- the repository root;
- a `docs/` folder;
- or a deployment branch such as `gh-pages`.

Given the desired layout, I would avoid naming the generated output `docs/`, because the site also has a `/docs/` URL area. Use `public/` locally, then either:

- publish `public/` to a `gh-pages` branch in CI; or
- configure GitHub Actions to upload `public/` as a Pages artifact.

Add a `CNAME` file containing:

```text
camplang.org
```

The custom domain should be managed from GitHub Pages settings and DNS. The site generator should simply preserve the `CNAME` file in the generated output.

## CI Workflow

The website repo should eventually have a GitHub Actions workflow:

1. Check out `camplang.org`.
2. Check out `dev` and `pkg.camplang.org` at pinned refs or sibling paths.
3. Install Zola.
4. Build the compiler if API docs are generated from the compiler.
5. Generate metadata.
6. Build the static site.
7. Publish `public/`.

For now, while the repos are local and releases are manual, a local build script is enough. CI can come after the first site shape is stable.

## Recommended Initial Implementation

Start with Zola and keep the first version deliberately small:

1. Create `camplang.org/content/_index.md`, `install.md`, and maybe `features.md`.
2. Create `camplang.org/tool/config.toml`, templates, Sass, and `build.sh`.
3. Import `dev/docs/language` into `/docs/language`.
4. Build into `camplang.org/public`.
5. Add a plain link to GitHub.
6. Add placeholder API docs pages that explain API docs are generated from metadata.
7. Add the real metadata-to-markdown generator after the first site is working.

The first milestone should be a usable static website with the language guide readable online. API docs can follow once the site navigation and style are settled.

## Decisions

- `public/` should be generated in CI for now, not treated as hand-maintained source.
- API docs should be generated by a C# tool for now.
- Compiler docs belong on the public website.
- Package docs should show the current contents of `pkg.camplang.org` until formal releases exist.
- The compiler repository will be `https://github.com/camplang-dev/camp`.
- The website will live in another repository under `https://github.com/camplang-dev`.

Working assumptions:

- Do not hand-edit generated output.
- Use Zola for the site and C# for metadata-to-markdown API generation.
- Publish language guide first, compiler docs alongside it, stdlib API second, package API third.
- Keep JavaScript optional and limited to search or small progressive enhancements.
