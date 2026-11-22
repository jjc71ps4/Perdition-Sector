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

Current NT4 finishes are default RUTex with the confirmed brown-tone correction,
black for Black/BLK, and original FDE for the other paints. The visibility and
distance changes are player-confirmed. The new black finish and a complete
fresh-PC installation remain user tests. The base includes all 17 confirmed
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
