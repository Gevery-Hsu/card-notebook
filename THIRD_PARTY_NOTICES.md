# Third-party notices

The repository's original application code is provided under MIT. Dependencies and upstream assets retain their respective licenses; installing this project does not relicense them.

- **shadcn/ui** components under `src/components/ui/` derive from shadcn/ui, copyright shadcn, MIT: https://github.com/shadcn-ui/ui/blob/main/LICENSE.md
- **Noto Sans SC / Noto Serif SC** are installed through Fontsource packages and bundled locally during builds. Noto fonts use the SIL Open Font License 1.1. Keep their license notices when redistributing built font assets: https://openfontlicense.org/
- **Lucide** icons use the ISC License: https://github.com/lucide-icons/lucide/blob/main/LICENSE
- React, Vite, Tailwind CSS, Radix, Milkdown, FastAPI, PyYAML, and other packages retain the notices distributed in their packages.
- **psycopg** is distributed under LGPL-3.0; its binary distribution includes additional libraries and notices. Consult the package's license before redistributing bundled binaries: https://www.psycopg.org/license/

This source repository does not vendor node_modules, Python environments, compiled font files, or platform deployment artifacts. See package-lock.json and requirements.lock.txt for the exact dependency versions.
