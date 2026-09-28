# Screenshot walkthrough

These are captures of the actual FreeCAD Lay Flat for CNC 0.12.8 interface on FreeCAD 1.1.3 for macOS. They use a small example cabinet with four panels and an unselected support block. The example sheet dimensions are not stock recommendations.

## 1. Optional panel tags

Check the components that are panels and leave fittings unchecked. **Save panel tags** remembers the choices in the model; save the `.FCStd` model to retain them between sessions.

![Panel Tags dialog with four panels checked and a support block excluded](images/01-panel-tags.png)

## 2. Choose parts and the fillet cutoff

The part picker shows each component and its current size. Tags provide defaults; you can change the selection for this layout. **Remove fillets up to** defaults to 1 mm, including exactly 1 mm. Set it to 0 to keep all fillets.

![Part picker showing the selected panels and adjustable 1 mm fillet cutoff](images/02-select-parts.png)

## 3. Set up and preview the sheets

Set quantities, rotation, grain, machining clearances and sheet dimensions. Each thickness gets its own stock settings. The preview updates automatically, or you can use **Update sheet preview**. Click **Create sheet layout** when ready; this does not export files.

Operation colours and layer names can also be edited in the table below the preview; scroll down if it is below the visible area.

![Sheet settings and preview with separate 6 mm and 18 mm stock](images/03-sheet-settings.png)

## 4. Inspect the layout

The generated FreeCAD document shows the arranged outlines and machining features. Colours distinguish operation layers. Different thicknesses stay on separate sheets.

![FreeCAD top view of the two example sheets](images/04-sheet-layout.png)

## 5. Read the operation tree

Expand **Sheet layouts — operations**, then a sheet. Matching operations are combined into one item per sheet. Hole diameters and depths are written explicitly. The sheet number appears in brackets, rather than as an unexplained duplicate-label suffix.

**Guides — not cuts** keeps reference geometry separate. The 3D copies are in their own initially hidden group.

![Model tree showing outside profiles, a 6 mm pocket, 5 mm holes and 35 mm holes grouped by operation](images/05-operation-tree.png)

## 6. Export from the tree

Right-click **Sheet layouts — operations** for **Export all sheets…**. Right-click an individual sheet for **Export this sheet…**. The image shows the export action contributed by the macro; FreeCAD may also show its standard context-menu actions.

![Export all sheets context-menu action](images/06-export-menu.png)

## 7. Choose the destination and package contents

Choose a format and an existing destination folder. For all sheets from a newly created layout, you can include the individual part drawings, STEP files and part lists. Each export creates a new folder and keeps previous exports.

![Export dialog with DXF and SVG selected and the complete package enabled](images/07-export-options.png)

## 8. Choose an export format

Standard DXF is R2004. SVG uses millimetres at 1:1 scale. **DXF and SVG** produces both. The separate Mozaik option writes R12 closed polylines.

![Format choices: DXF, SVG, DXF and SVG, and Mozaik R12 DXF](images/08-export-formats.png)

## 9. Use the Mozaik preset

For Mozaik's part-import workflow, export all sheets with the complete package enabled and use the individual-part `_R12.dxf` files. Do not use the nested `Sheet_*` files as individual parts. Select millimetres on import and assign tools in Mozaik. Guides and labels are omitted from the R12 drawings.

An independent DXF reader checked the R12 structure and geometry. **Actual import into Mozaik remains unverified.**

![Mozaik R12 export option and its import instructions](images/09-mozaik-r12.png)

After exporting, the completion message gives the saved folder and an **Open export folder** button. Save the FreeCAD sheet layout normally if you want to reopen it and export again later; the complete macro package must be installed for the right-click actions to restore.

[Return to the main README](../README.md)
