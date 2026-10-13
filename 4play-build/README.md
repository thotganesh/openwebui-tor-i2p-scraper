# 4play-build

Build context for the `fourplay` container.

## Files

- `Dockerfile` — image definition (MIT, kept in this repo)
- `package.json` — Node dependencies (MIT, kept in this repo)
- `page-render.js` — **downloaded at install time** from the upstream project

## Why page-render.js is not in this repo

The upstream `4play` bridge is licensed **AGPL-3.0-only**. This project is MIT. To avoid a license conflict, `install.sh` downloads `page-render.js` directly from the upstream repository on first run:

    https://git.lolcat.ca/lolcat/4get/raw/branch/master/extra/4play/page-render.js

If you cloned this repo with `git` and want to build manually, run `install.sh` once (it downloads the file), or fetch it yourself:

    curl -fsSL "https://git.lolcat.ca/lolcat/4get/raw/branch/master/extra/4play/page-render.js" \
        -o 4play-build/page-render.js

## Credits

- [4get](https://git.lolcat.ca/lolcat/4get) by [lolcat](https://lolcat.ca) — AGPL-3.0
- [4play](https://git.lolcat.ca/lolcat/4get/src/branch/master/extra/4play) — AGPL-3.0
