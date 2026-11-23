# Perdition incremental updates

Setup/updater 0.2.3-beta.1 uses **beta-v2.json**. It installs the confirmed radio
recovery followed by the 67.6 MB asset/performance revision package over the
unchanged beta-2026.11.20.1 base snapshot. Legacy beta.json remains available
for the older radio-only updater. Upgrade once to the new setup bundle for
the current channel and its targeted profile migrations.

Run Update existing Perdition.cmd from the extracted current setup bundle,
selecting the installed folder containing ModOrganizer.exe. New installations
receive all applicable updates automatically. A successful existing-install
update also refreshes its persistent updater and channel configuration.

Each archive and changed file is verified by size and SHA-256. Replacements
require the expected predecessor or already-current contents. Profile actions
enable the named patches, disable four redundant mod entries and set only the
six approved distance values. Personal resolution, unrelated settings and saves
are retained. Assets and profile settings are backed up and share a rollback
transaction; unrecognized custom file contents or distances stop that update.

Current NT4 finishes include rifle-matched Urban, Desert Hex, Brush, Splinter
and Black Hex patterns with preserved proportions and physical scale. Desert Hex
Black and Black/BLK use plain black. Default RUTex and remaining FDE paints are retained. The visibility and
distance changes are player-confirmed. The latest intro-menu correction awaits native 5120 x 1440 confirmation. The base includes all 17 confirmed
subway repairs. No full base re-upload was needed for these revisions.

Player assets and setup binaries are immutable release downloads. This Git tree
contains source, manifests and publication receipts. Transport objects used by
the publisher are not files in the repository tree or part of ordinary clones.


The nt4-geometry-0.1.3 entry contains only the two NT4 NIF meshes from the
November 22 in-game-approved size/alignment adjustment. It uses a 905 KB ZIP
hosted in updates/, following the existing radio patch's raw-GitHub download
route. Materials, textures and paint mappings are unchanged. Updater/setup
0.2.3 and newer already support it; no new installer is required. New installs
apply it after prior patches. Existing players run Update Perdition Sector.cmd.



The lexington-repair-0.2.0 and concord-repair-0.3.0 entries contain player-confirmed native geometry and visibility repairs. They enable PSLexingtonOptimization.esp before PSConcordOptimization.esp through the existing profile migration mechanism. The intro-viewport-0.1.17 entry replaces only PSNewGameMenu.swf, using the published predecessor checksum. Its layout simulations pass; native 5120 x 1440 confirmation is pending. Setup/updater 0.2.3 and later already support these three entries. The optional setup 0.2.5 asset addresses Steam session/QR recovery.



The nt4-camos-0.1.6 entry contains the player-approved final camo textures, materials and paint mappings. It combines the November 23 camo work through Splinter, with the aspect-ratio correction, as one update over the published NT4 patch. It adds no profile migration and needs no installer rebuild.
