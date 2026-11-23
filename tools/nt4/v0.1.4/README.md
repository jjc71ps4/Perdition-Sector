# NT4 matching rifle camos 0.1.4

This local update adds matching NT4 suppressor finishes to Urban, Desert Hex,
Brush, and Desert Hex Black 2 Electric Boogaloo. Paint samples come from the
installed MK18 Deluxe rifle textures. Cylindrical paint coordinates are baked
into the existing NT4 game UVs. The repaired surface detail remains visible.

Four new 4096-pixel BC7 sRGB diffuse textures include full mip chains. Four BGSM
materials retain the existing NT4 normal, specular, cubemap and shader settings.
The existing ESL-flagged Perdition_NT4_Repaired.esp changes only the two KAC
material destinations in each of the four selected paint MSWP records, plus its
descriptive header. Both KAC mesh variants use these mappings. All other record
fields and paint options are preserved. No mesh or saved Blender file changes.

Run prepare_sources.py, run bake_camos.py inside the saved replacement Blender
project, then run stage_and_validate.py and install_camos.py with MO2 and the
game closed. Start Blender with a neutral working directory such as C:\workspace;
the game directory contains DLLs that interfere with Blender startup.

Validation compares all 17 existing patch records, verifies the exact eight
changed suppressor destinations and all unchanged fields, checks DDS format and
mips, and checks original geometry, finish and profile file hashes. Native Blender
renders inspect both sides. In-game lighting and workbench switching still need
user confirmation. Restart the game and select each existing paint option;
reapply the paint if the current weapon is displaying a cached material.

installation_receipt.json records backups, installed hashes and visual-test
status. rollback_camos.py restores the previous plugin and removes only the eight
new files after checking their installed hashes. The previous mesh alignment,
default RUTex finish and BLK finish remain in place. Publication is separate.
