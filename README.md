# Mestra Lay Flat 0.12.0

A portable FreeCAD macro bundle for tagging panels, choosing parts manually, and exporting flat sheet layouts. It works from solid CAD geometry, including imported STEP parts. No Mestra cabinet template or customer model is included or required.

**[Download the complete ZIP](https://github.com/getmora/mestra-lay-flat/releases/download/v0.12.0/Mestra-Lay-Flat-0.12.0.zip)** · [Release notes](https://github.com/getmora/mestra-lay-flat/releases/tag/v0.12.0)

## Install

1. Extract the entire ZIP into a folder. Keep the macros and SVG icons together.
2. In FreeCAD, use **File → Open** to open `Install_Mestra_Lay_Flat.FCMacro`, then choose **Macro → Execute Macro** with that editor active. If asked, select the extracted folder.
3. Use **Panel Tags** and **Lay Flat** in the **Mestra** toolbar. If the toolbar cannot refresh during an active edit, finish that edit and switch workbenches, or restart FreeCAD.

The installer uses the configured FreeCAD macro folder. It preserves existing toolbar buttons, backs up older files before replacing them, and avoids duplicate commands when run again. No Python packages need to be installed separately.

Tested on **FreeCAD 1.1.3 on macOS**. Paths are portable and use FreeCAD's settings; Windows and Linux have not yet been tested. The automatic installer requires FreeCAD's `Gui.Command.createCustomCommand` API.

### Manual installation

Copy `Mestra_Flat_Export.FCMacro`, `Mestra_Panel_Tags.FCMacro`, and both SVG icons into the macro folder shown in **Macro → Macros**. Run either macro from that dialog. The installer is only needed to add the toolbar buttons automatically.

## Tag once, choose each time

1. Select one or more finished parts in the tree or 3D view. Click **Panel Tags**, review the list, and choose **Tag as panels**. Use **Remove panel tags** to clear them. Whole assemblies and groups are not automatically tagged.
2. Save your model as a FreeCAD `.FCStd` file to retain the tags. STEP files do not store these FreeCAD properties. Tags add metadata only; they do not alter geometry. Tag changes can be undone.
3. Select an assembly/subassembly to limit the scope, or clear the selection to use the visible model. Click **Lay Flat**, review the checkboxes, and continue to sheet settings and export.

Tagged panels start checked. Individually selected solid parts also start checked even when untagged. Other solid parts remain available to select manually. **Select tagged panels**, **Select shown**, **Clear all**, and search help manage the list. Selecting a row highlights its source component in FreeCAD.

Names, file origin and thickness never automatically exclude a solid part. A part named “drawer side” remains available, as does a STEP-imported panel. Unticking a part for one export does not remove its saved tag. A search filter does not uncheck hidden rows; the selection count reports selected rows hidden by the search.

The saved Boolean property is **LayFlatPanel**, under **Lay Flat** in the Data properties. A tag on a local component overrides a tag on its linked source, including an explicit False value. Source tags can be inherited by links. A component reused in multiple assembly placements shares its tag; the export picker still lists each placement separately. A multi-solid component's tag applies to all of its solids. Use separate component objects if you need separate saved tags.

The tagging command does not automatically edit external source documents. Tag a local component link, or open its source model explicitly if you want to tag that source definition.

## Thickness and stock

Thickness is measured **after** you choose parts. There is no 6/18/30 mm whitelist. For example, selected 12 mm and 16 mm panels get their own sheet-settings sections. Sheet settings include dimensions, margins, machining gap, grain direction and rebate extension.

The macro never scales a model to match a stock thickness. Different detected thicknesses are kept on separate sheets. Same-thickness parts are assumed to use the same material; export different materials separately.

## What can be exported

- Valid solid CAD panels with a broad planar face; imported STEP solids and native parts are handled alike.
- Supported planar recesses, perpendicular holes/drill tips, ruled tapers and convex edge roundovers.
- Exact straight-line and circular-arc operation boundaries.
- Each placed assembly instance is counted separately; user-entered quantities are applied afterwards.

Meshes, sketches and construction geometry are not manufacturing solids. Unsupported side/angled drilling, freeform boundaries, ambiguous thickness and other unsupported machining produce an error for the selected parts. Unsupported unselected solid geometry does not prevent reaching the picker. Unresolved component links and structural assembly errors still need to be repaired.

Selecting a broad planar face can guide flattening when automatic thickness detection is ambiguous. Linked arrays need to be expanded to individual component links; quantities are not guessed from an array.

## Outputs and limits

The exporter writes to a new output directory. It includes sheet DXFs, individual part outputs, exact STEP solids, `Flat_parts.FCStd`, a manifest, quantities and machining notes. The source model is not flattened or modified by export.

The chosen upper face is used for the sheet DXF. Underside operations remain documented in the notes/manifest and exact 3D geometry. Taper and roundover reference layers are not finished cutter paths. Set tooling, compensation, depths and machining setups in your CAM software. Sheet placement is rectangular packing, not an optimal-yield guarantee.

## Files

- `Install_Mestra_Lay_Flat.FCMacro` — portable installer and toolbar setup.
- `Mestra_Panel_Tags.FCMacro` — tag/remove-tag command.
- `Mestra_Flat_Export.FCMacro` — manual selection, geometry analysis and export.
- `mestra-panel-tags.svg`, `mestra-lay-flat.svg` — toolbar icons.
- `SHA256SUMS.txt` — checksums for the release files.

Distribute the complete ZIP so the tagging command can find the matching exporter. The Assembly Builder and your cabinet master files are separate and are not included.
