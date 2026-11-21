# Perdition Sector — Beta

Perdition Sector is Faust's tactical horror shooter built inside Fallout 4.
It features high-lethality combat, light discipline, a randomized HVT campaign,
and New Game Plus with persistent equipment and rerolled objectives.

This project is in beta. It requires a Steam account that owns Fallout 4 and
all six gameplay DLCs. The installer downloads the compatible game depots from
Steam using your account, builds a separate Fallout 4 1.10.163 instance, installs
F4SE 0.6.23, and configures the Perdition Mod Organizer profile.

## Install this beta

1. Download [Perdition Sector Setup 0.2.0-beta.1](https://github.com/jjc71ps4/Perdition-Sector/releases/download/beta-2026.11.20.1/Perdition_Sector_Installer_v0.2.0-beta.1_Beta.zip).
2. Extract the setup ZIP and run `PerditionSetup.exe`.
3. Leave **Download the package automatically** selected. Choose a new install
   folder, your resolution, and whether to enable ENB. ENB is optional and off
   by default.
4. Sign into Steam when prompted and allow setup to finish. Keep Steam open
   when playing. Launch using `Launch Perdition Sector.cmd` or MO2's F4SE entry.
5. Start a New Game and enter your name and gender. Jug's preset applies
   automatically, and Side Aim no longer requires a manual restart.

Mouse5 holds the momentary flashlight; Mouse4 activates Side Aim. The former
ECO fire-mode binding is unbound in this beta.

Use a drive with ample free space: approximately 90 GB for the installed game
and mods, plus the downloaded archive. During package download and assembly,
setup temporarily retains both the archive parts and assembled ZIP. The final
archive size is recorded on the release page. The existing Steam installation
and other mod builds are preserved.

The numbered payload files are release assets. Setup downloads, verifies and
joins them automatically. They are not separate playable mods. GitHub's
automatically generated **Source code** ZIP is not the player build.

## Current limitations

- Grass rendering remains unresolved.
- Rain/precipitation may disappear while NVGs are active.
- Some museum floors/precombines require repair.
- All 17 subway poster repairs are included and confirmed working by Faust.
- The next-generation Fallout 4 runtime is not supported by this build.

## Project contents

The repository contains the installer and publishing source plus the frozen
release manifests. Large player assets are attached to the beta release.
Personal saves, account credentials, editor caches, Creation Kit and downloaded
Fallout game depots are excluded from the snapshot. Third-party components
remain the work of their respective authors; the Perdition gameplay, campaign,
integration and custom modifications are Faust's work.

See [release notes](RELEASE_NOTES.md) and [publishing instructions](publisher/README.md).

