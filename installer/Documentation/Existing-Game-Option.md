# Reuse a downgraded Fallout 4 installation

The default flow detects compatible game folders or requires the player to
select the folder containing Fallout4.exe. The executable must report 1.10.163;
base-game archives and all six DLC masters/main/texture archives must exist.
An incompatible/missing game is rejected before the large PS package download.

Existing mode skips Steam login and depot retrieval, reuses the selected folder,
installs matching F4SE, and deploys the PS mod/profile package separately. MO2's
game path and all executable paths use that same selected directory. Changed
existing F4SE/control/root files are backed up beneath the PS installation;
ENB deactivation storage is also kept there rather than beside the external game.

The original Steam download path remains available as an explicit option.
Both modes use the already published GitHub package with its pinned manifest.
Setup version 0.2.1-beta.1 is independent of payload version 0.2.0-beta.1.

This local candidate is not uploaded to GitHub. The existing published build
package is not changed. Actual installation/gameplay on a different PC still
requires testing.
