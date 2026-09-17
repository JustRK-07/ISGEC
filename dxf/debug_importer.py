#!/usr/bin/env python3
"""Debug: what does Importer do to top-level INSERT coordinates?"""

import ezdxf
from ezdxf.addons.importer import Importer

MECH = "/home/rushabh/Desktop/Rushabh New Laptop Files/desktop/Rushabh/edi_sem_5/ISGEC/dxf/TP-104 MECH GA_clean2.dxf"
STR  = "/home/rushabh/Desktop/Rushabh New Laptop Files/desktop/Rushabh/edi_sem_5/ISGEC/dxf/TP-104 STR GA_clean3.dxf"

out_doc = ezdxf.readfile(MECH)
str_doc = ezdxf.readfile(STR)

print("Original STR INSERTs for GridLine-* blocks:")
for e in str_doc.modelspace():
    if e.dxftype() == 'INSERT' and 'GridLine' in e.dxf.name:
        x, y = e.dxf.insert[0], e.dxf.insert[1]
        print(f"  {e.dxf.name[-15:]:<20}  pos=({x:.1f},{y:.1f})  xscale={e.dxf.xscale}")

imp = Importer(str_doc, out_doc)
for str_block in list(str_doc.blocks):
    if str_block.name.startswith("*"): continue
    imp.import_block(str_block.name, rename=False)

for entity in list(str_doc.modelspace()):
    try:
        imp.import_entity(entity, target_layout=out_doc.modelspace())
    except Exception:
        pass
imp.finalize()

print("\nAfter import (BEFORE my transform), INSERTs to GridLine-* blocks in out_doc:")
for e in list(out_doc.modelspace()):
    if e.dxftype() == 'INSERT' and 'GridLine' in e.dxf.name:
        x, y = e.dxf.insert[0], e.dxf.insert[1]
        print(f"  {e.dxf.name[-15:]:<20}  pos=({x:.1f},{y:.1f})  xscale={e.dxf.xscale}")
