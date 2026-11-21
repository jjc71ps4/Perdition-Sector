# Perdition incremental updates

The beta channel applies small, ordered updates to the existing
`beta-2026.11.20.1` snapshot. The 34 GB base archive is unchanged.

Radio recovery 0.1.1 replaces only `overwrite/Scripts/PSRadioQuestScript.pex`.
The player confirmed broadcast playback returned in an existing save without
a new game or console restart. The log records automatic recovery of a stopped
scene on load. The complete stalled-scene watchdog path is not independently
confirmed by that log.

Setup 0.2.2-beta.1 or later checks this index after installing the base package.
Existing players use the matching updater, selecting their installed Perdition
folder; it downloads only missing patches. Older installers need that one-time
updater upgrade. The installer itself is distributed separately.

Each archive and file has a SHA-256, and each replacement has an expected old
hash. Already-current or later released content is preserved, custom changes
are rejected, and changed files are backed up before replacement. Updates do
not run Steam downloads, re-extract the base package or touch player saves.
Close Fallout 4 and MO2 before updating, then restart the game normally.

Keep versioned archives immutable. Append later updates in order, with the
expected predecessor hash for each file. Larger updates can use release-asset
URLs. The current updater accepts patches up to 500 MB and limits file writes
to mods/overwrite within the chosen Perdition installation. Content requiring
profile migration needs a dedicated migration rather than replacing personal
settings wholesale.

The unconfirmed rendering-distance experiment and visibility repair work are
not part of this update.
