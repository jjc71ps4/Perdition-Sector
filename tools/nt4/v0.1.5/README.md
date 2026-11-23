# NT4 camo aspect and scale correction 0.1.5

Faust found the four new camos nearly perfect, but requested that their pattern
aspect ratios be preserved and their size match the rifle. The prior cylindrical
map tuned axial and circumferential repeats independently. It also inferred the
cylinder center from a bounding box that included the asymmetric mounting latch.

The correction measures each paint sample's actual UV-to-world Jacobian on the
visible rifle receiver. That complete two-dimensional metric, including the
small source shear, maps physical axial distance and circumferential arc length
to the paint texture. A fitted can-body circle excludes the latch and inner wall.
The pattern is never scaled independently in U and V to fill the suppressor.
End-facing surfaces use planar physical coordinates instead of a pinched polar
map. A narrow, 10-degree underside closure crossfades two unscaled samples.

Four diffuse DDS files change. All BGSM material settings, normal/specular maps,
ESPs, NIFs, saved Blender authoring files, original FDE and BLK finishes, default
RUTex, and profile configuration remain byte-identical. Existing paint choices
and both KAC mesh material paths continue to work without new records.

For each camo, 4,589 outer-body triangles outside the closure and 1,002 flat
end-facing triangles were compared with the rifle source metric. Maximum body
aspect error is 0.242%; maximum physical-scale error is 0.199%. These bounds apply
to the sampled principal surfaces, not all bevels, recesses or the closure blend.
Previous median aspect error was approximately 22.3% Urban, 7.2% Desert Hex,
50.3% Brush, and 7.2% Black Hex. This measures surface proportions, not screen
foreshortening caused by viewing a curved object.

The default RUTex was audited separately using 144 samples of its existing direct
surface-ray projection. It does not use the independent-repeat code. Its median
local aspect difference from the old suppressor is 3.7%, attributable to different
cylinder shapes. Its already-approved colors and transfer remain intact. Solid
FDE and black have no camo pattern aspect ratio to adjust.

Native Blender comparison renders show the new camos with flat rifle-scale
reference strips. The exact metrics are in aspect_validation.json. Conversion
checks verify 4096-square BC7 sRGB DDS files, 13 mip levels and decoded-pixel error.
installation_receipt.json records before/after hashes and exact backups.
rollback_textures.py restores only these four textures after version checks.

Run audit_projection.py, measure_surface.py, bake_metric_camos.py and
validate_surface_metrics.py in the saved replacement Blender project. Start
Blender from C:\workspace to avoid the game directory's DLL search path. Then run
stage_textures.py and install_textures.py with game/MO2 closed. This version is
installed locally for visual review; no GitHub/channel publication is implied.
