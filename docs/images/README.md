# Screenshot assets

These PNGs are direct captures of the running application, not generated interface concepts. All note text, tags, and book sources are fictional examples prepared for documentation. They contain no private notes or deployment details.

| File | Content | Capture size |
| --- | --- | --- |
| home-light.png | Light card feed | 1440 × 1080 |
| home-dark.png | Dark card feed | 1440 × 1080 |
| reading.png | Long-form Markdown reader | 1440 × 1080 |
| editor-tags.png | Rich-text editor and inline tag editing | 1440 × 1080 |
| categories.png | Category manager, names, drag handles, and icon picker | Cropped to the actual dialog |
| mobile.png | Responsive mobile card feed | 390 × 1000 |

Only screenshots are included. No example database or startup seed is bundled, so a new deployment still starts empty with the four default categories.

To update these assets, start a local instance with an explicitly isolated `NOTEBOOK_DATA_DIR`, add fictional examples, wait for bundled fonts to load, capture the actual UI, and inspect every image before committing. Never use a personal notebook or a production deployment for documentation screenshots.
