# Perdition Sector: Lexington, Concord, intro viewport and setup repairs

- Lexington: rebuilt precombines and visibility for 18 exterior cells. Player confirmed the repair in game.
- Concord: rebuilt 18 exterior cells plus the Museum of Freedom and Civic Access interiors. Player confirmed the repairs in game.
- Cosmetic scenery deletions remain in place; the generated geometry and visibility now reflect them. Corrected combined-material handling and alpha exclusions are included.
- Intro name/gender menu: place and fit controls within Scaleform's actual visible viewport, including its origin. The compiled menu passes 27 layout-bound checks, including 5120 x 1440. Native ultrawide confirmation is pending.
- Setup 0.2.5-beta.1: automatic Perdition download; one Steam downloader session for the pinned game/DLC packages; bounded token/QR recovery without password prompts when QR mode is selected. Mocked Steam recovery tests pass; this is still a beta installer.

Existing players: close Fallout 4 and MO2 and run `Update Perdition Sector.cmd`. Players without that command can extract the setup ZIP and use `Update existing Perdition.cmd`.

The unchanged public updater 0.2.3 applies all three new content updates, enables both area patches in dependency order, and verifies 2,061 resulting files in an offline fixture. Repeating the update downloads nothing. The fixture preserved 5120 x 1440 preferences and a save sentinel. Network downloads were mocked in this fixture; release assets are separately verified by the publisher.

No new installer is required for these content updates. Setup 0.2.5 is provided for the earlier Steam authentication failure. No base snapshot re-upload, save migration, gameplay rebalance, or graphics-distance change is included in this release. Grass and NVG precipitation issues remain open.
