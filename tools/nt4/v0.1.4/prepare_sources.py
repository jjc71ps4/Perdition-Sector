"""Extract paint-only swatches from the installed rifle's actual camo atlases."""
from pathlib import Path
import hashlib, json
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
MOD = Path(r'C:\Perdition Sector\mods\MK18 Deluxe (Faust Edit)')
OUT = HERE / 'Sources'
OUT.mkdir(exist_ok=True)
configs = [
    ('Urban', 'Urban/MK18_D.DDS', (2940, 3820, 4020, 3910), 1.0, 'mk18_deluxe.esp:00006B'),
    ('Desert_Hex', 'Desert_Hex/MK18_D.DDS', (3720, 1140, 4010, 1310), 1.8, 'mk18_deluxe.esp:000066'),
    ('Brush', 'Brush/MK18_D.DDS', (2820, 3820, 3180, 3910), 1.65, 'mk18_deluxe.esp:00006C'),
    ('Black_Hex', 'Desert_Hex/MK18_BLK_D.DDS', (3720, 1140, 4010, 1310), 1.8, 'mk18_deluxe.esp:000068'),
]
rows = []
for slug, texture, crop, repeat, key in configs:
    src = MOD / 'Textures/Weapons/MK18/MK18/Skins' / texture
    im = Image.open(src).convert('RGB')
    paint = im.crop(crop)
    # The hex atlas has a fine engraved panel outline. Suppress that old
    # rifle-specific detail; the new NT4 supplies its own lettering and wear.
    if slug in {'Desert_Hex', 'Black_Hex'}:
        paint = paint.filter(ImageFilter.GaussianBlur(3))
    path = OUT / (slug + '_paint.png')
    paint.save(path)
    rows.append(dict(slug=slug, source_texture=str(src), source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
                     source_size=im.size, crop=crop, paint_path=str(path), axial_repeat=repeat,
                     circumference_repeat=2 if slug in {'Desert_Hex', 'Black_Hex'} else 6,
                     source_detail_filter_radius=3 if slug in {'Desert_Hex', 'Black_Hex'} else 0,
                     material_swap=key))
(HERE / 'paint_sources.json').write_text(json.dumps(rows, indent=2))
print(json.dumps(rows, indent=2))
