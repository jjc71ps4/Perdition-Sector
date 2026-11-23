# Perdition Sector Setup 0.2.5-beta.1 - automatic Steam session recovery

This installer downloads the existing 0.2.0-beta.1 Perdition build package from
GitHub, then applies the small verified updates listed in its public beta channel.
The base game package and its checksums are unchanged. The installer itself is
distributed separately; the updated installer and revision archive are separate release assets.

Already installed Perdition? Run `Update existing Perdition.cmd` and select the
Perdition folder containing ModOrganizer.exe. This checks only the small update
channel: it does not download the 34 GB base package, run Steam downloads, or
replace personal resolution settings or saves. Close Fallout 4 and MO2 first.
New installations receive `Update Perdition Sector.cmd` in their game-pack root
for later checks. Existing players using this setup ZIP can keep using its
`Update existing Perdition.cmd` without reinstalling.

The first update is the player-confirmed Radio Recovery 0.1.1, a 3.2 KB ZIP
containing only the changed compiled radio script, followed by the 67.6 MB
confirmed-revisions archive. Each archive and file has a
size/SHA-256 check. Replaced files are backed up, already-current or later released
versions are retained, and unexpected custom changes stop the update without
overwriting that file. Do not manually edit the update index to bypass a mismatch.
The confirmed performance settings and visibility patch, NT4 replacement and finishes,
and attachment-path fixes are applied by the revision update. Profile migration
enables the new plugins and updates only the approved distance keys; resolution,
unrelated preferences and saves are preserved. Black/BLK selects black, Standard
selects RUTex, and the other paint options select original FDE.

Existing-game mode remains available for a Fallout 4 installation you already
downgraded. Older installers require this one-time updater/installer upgrade;
they cannot discover a patch channel they were never programmed to read.

1. Extract the entire setup ZIP and run `PerditionSetup.exe`.
2. Perdition Sector downloads automatically from GitHub. No package selection is needed.
3. Choose the new Perdition installation folder for MO2, mods and the profile.
4. **Use existing downgraded Fallout 4** is selected by default. Setup searches
   common Steam libraries and compatible game folders. If needed, browse to
   the folder containing `Fallout4.exe`.
5. Setup requires Fallout 4 **1.10.163**, the base-game assets and all six DLCs.
   A missing or incompatible game shows the requirement prompt and blocks
   installation until a valid folder is selected.
6. Existing-game mode skips Steam account entry, DepotDownloader and all Steam
   game/DLC downloads. The selected game folder is used directly; it is not
   duplicated into another `_Fallout4` folder.
7. Alternatively select **Download compatible game from Steam** and leave
   **Use Steam mobile QR login** checked. Scan once with the owning Steam account;
   all 14 pinned game/DLC packages download and validate in that same session.
   No login name or password is needed in QR mode. If QR polling fails after
   sign-in, setup automatically resumes with the authenticated account token.
   A missing/rejected token receives fresh QR authentication; password prompts
   are disabled throughout this QR flow. Authentication retries are bounded.
   Existing downloads are retained and revalidated. Password login remains
   optional when QR login is unchecked.
8. Choose resolution, optional ENB and shortcut settings, then Install / Resume.

Existing-game mode still installs the matching F4SE 0.6.23 and required PS root
files into the selected game folder. Original files that it replaces are kept
under `_Installer/ExistingGameBackup` in the Perdition installation. The game
executable and base/DLC archives are preserved. MO2, all executable entries and
the launcher are configured to use the selected game directory.

The Perdition payload is about 34 GB compressed and 41.6 GB installed. Package
download/assembly also needs temporary space for the parts and complete ZIP.
Existing-game mode does not reserve another 44 GB for a second game copy.
Steam must still be available when playing a Steam copy of Fallout 4.

The unchanged payload includes the confirmed 17 subway repairs, approved New
Game/audio flow, automatic Jug settings and Side Aim, the cyan panoramic NVGs
without grain, flashlight/radio fixes and compact splash launcher. Existing
grass and NVG precipitation issues remain. Lexington and Concord/Museum repairs are delivered through the update channel.

This is a test candidate: fixture and UI checks do not replace a fresh-PC
installation/gameplay test. No full installation was run on the development PC.
