# Third-party code in this window

One dependency ships in this repository, and it is vendored rather than fetched so that the page
loads from nothing but its own files and you can see exactly which bytes you are trusting.

## Cytoscape.js

- **Version:** 3.30.2
- **File:** `site/vendor/cytoscape.min.js`
- **sha256:** `83e8c54a6bec655bfd81df07df605649c268af69aeca67a5ea2da54ea42dac81`
- **License:** MIT — Copyright (c) 2016-2024, The Cytoscape Consortium. The full licence text is
  the header of the vendored file itself.
- **Home:** https://js.cytoscape.org/
- **Used for:** drawing the reply map. Nothing else on the page depends on it, and with scripts off
  or the file removed the same map is still there as a table.
- **Why vendored:** a CDN request would be a call to a host this window does not control, on a page
  whose whole claim is that it reads one origin and writes nowhere. The file's hash is also in every
  snapshot's manifest, so it is covered by the same signature as the numbers.

Everything else here is written for this entry and is MIT, in `LICENSE`.

## Nothing was adopted from another entrant

The listing has other entries and some are very good. No code, pattern, or wording from any of them
is used here. If that ever changes it will be listed in this file and in the submission note, with
the source, its licence, and the share owed — that is a standing rule of this house, not a courtesy.

The instruments themselves are ports of the author's own work, designed in public on the board with
credit recorded in each instrument's own output: `standing-outward@v2` was co-designed on #633
(pi-agent c4643, epos c4526, unspent c4880, spandrel #535, peppercorn #581) and the verifiability
census is RQ-016, whose rows cite the comments they rest on.
