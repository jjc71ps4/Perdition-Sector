# Perdition Sector Setup 0.2.0-beta.1

This setup installs the November 20 beta snapshot from its GitHub Release.
A Steam account owning Fallout 4 and all six gameplay DLCs is required.
Compatible Fallout 4 1.10.163 depots are downloaded directly from Steam using
your account. Your existing Steam installation is preserved.

1. Extract this entire ZIP, then run `PerditionSetup.exe`.
2. Leave **Download the package automatically** selected.
3. Choose a new installation folder outside Windows/Program Files, your
   resolution and Steam login name. Setup may share its otherwise-empty folder
   with the installation.
4. ENB is optional, off by default, and brightens the image when enabled.
5. Select **Install / Resume** and complete Steam authentication when prompted.
   The remembered account is reused for subsequent depot downloads.
6. Keep Steam open and run `Launch Perdition Sector.cmd` after setup completes.
   MO2's F4SE entry is also supported.

Allow roughly 90 GB for the installed game/mods plus the downloaded archive.
Downloading and joining archive parts temporarily requires room for both
copies. The exact archive size is recorded in `package_source.json`.

New Game asks for your name and gender. Stats are locked, leveling remains
disabled, Jug's preset loads automatically and Side Aim initializes without the
old manual restart step. Mouse5 is the momentary flashlight; Mouse4 is Side Aim.

This is a beta. Grass rendering, precipitation while using NVGs and museum
floor/precombine damage remain unresolved. All 17 subway poster repairs are
included and confirmed working by Faust. The approved cyan
panoramic NVG mask is included without experimental grain or ReShade.

The source is pinned to this beta tag and checksum. Completed downloads are
retained when setup stops so you can retry. Do not substitute another beta's
package. Your existing saves and original account settings are not bundled.

The extra full-archive scan remains disabled for beta diagnosis at the author's
request. Download part hashes, assembled ZIP SHA-256, World plugin hash, pinned
dependencies and installed runtime checks remain enabled.

The repository's Source code ZIP is authoring material, not the player payload.
Python and GitHub CLI are not needed on a player's PC. Use the Windows setup.
No full installation is run on the authoring PC while building this package.
