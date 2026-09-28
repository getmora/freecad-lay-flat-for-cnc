# FreeCAD Lay Flat for CNC

Turn the panels in a FreeCAD model into flat sheet layouts for CNC preparation.

For example, open a cabinet model, choose its sides and shelves, and arrange flat copies on sheets of plywood. The tool measures their thickness, keeps different thicknesses on separate sheets, and exports drawings you can open in your CAM software.

**Your original model stays in place.** The tool exports separate copies; you do not need to dismantle or flatten your assembly by hand.

**[Download version 0.12.4 — complete ZIP](https://github.com/getmora/freecad-lay-flat-for-cnc/releases/download/v0.12.4/FreeCAD-Lay-Flat-for-CNC-0.12.4.zip)** · [Release notes](https://github.com/getmora/freecad-lay-flat-for-cnc/releases/tag/v0.12.4)

## What it does

- Lets you choose exactly which solid parts to export, including parts imported from STEP files.
- Lays the parts flat and arranges them on sheets, with settings for sheet size, spacing, quantities, rotation and grain direction.
- Exports sheet DXF drawings, individual part drawings, 3D manufacturing copies and part lists.
- Lets you remove small finishing fillets from export copies, with an adjustable radius and support for mirrored parts.
- Optionally remembers which components are panels, so they start checked next time.

**This prepares geometry for CAM; it does not generate G-code.** You still set up cutters, cutting depths, toolpaths and machine settings in your CAM software.

## Before you start

You need FreeCAD and a model containing solid panels. Native FreeCAD parts and imported STEP solids are supported; meshes such as STL files are not. No cabinet template is required or included.

The documented tested setup is **FreeCAD 1.1.3 on macOS**. Windows and Linux compatibility has not yet been verified. The automatic toolbar installer needs FreeCAD's macro-toolbar support; if it reports that this is unavailable, use the manual installation below.

The tool runs as FreeCAD macros: small scripts opened inside FreeCAD. You do not need a terminal, coding knowledge or a separate Python installation.

## Install

1. **Download and extract the complete ZIP** using the link above. Keep all the extracted files together, including the three `.FCMacro` files and two `.svg` icons.
2. **Run the installer inside FreeCAD.** Choose **File → Open** and open `Install_FreeCAD_Lay_Flat_for_CNC.FCMacro` from the extracted folder. With that file's editor tab active, choose **Macro → Execute Macro**. If a folder chooser appears, select the extracted folder.
3. **Look for the “FreeCAD Lay Flat for CNC” toolbar.** It contains **Panel Tags** and **Lay Flat for CNC**. If it does not appear, finish any active edit and switch workbenches, or restart FreeCAD.

To update an existing installation, repeat these steps with the new ZIP. The installer backs up older files before replacing them and preserves other toolbar buttons. Close any open Lay Flat dialog, then launch **Lay Flat for CNC** again to use the updated macro.

<details>
<summary>Manual installation — if the toolbar installer does not work</summary>

1. In FreeCAD, open **Macro → Macros** and find the macro folder shown in that dialog.
2. Copy these four files from the extracted ZIP into that folder: `FreeCAD_Lay_Flat_for_CNC.FCMacro`, `Panel_Tags.FCMacro`, `lay-flat-for-cnc.svg` and `panel-tags.svg`.
3. Return to **Macro → Macros**, select `FreeCAD_Lay_Flat_for_CNC.FCMacro` or `Panel_Tags.FCMacro`, and run it. You can use both tools this way without toolbar buttons.

</details>

## Make your first export

You can export straight away. **Panel tagging is optional.**

### 1. Choose your parts

Open your model in FreeCAD, then decide what to include:

- **One or more parts:** select them in the model tree or 3D view.
- **A cabinet or subassembly:** select it to review the parts inside it.
- **The visible model:** clear your selection before starting.

Click **Lay Flat for CNC**. In **Choose parts to lay flat**, check the panels you want and leave hinges, screws and other fittings unchecked. Click a row to highlight the original component in FreeCAD.

Individually selected solid parts and previously tagged panels start checked. Selecting a whole cabinet does **not** automatically check all its contents. You can check other solid parts manually, regardless of their name or thickness.

Before clicking **Continue**, check **Remove fillets up to** below the part list. This controls whether small rounded edges are removed from the manufacturing copies:

- **1 mm (default):** remove supported fillets of 1 mm or less, including exactly 1 mm. Larger fillets remain.
- **Another radius:** include fillets up to and including that radius.
- **0 — Off:** keep all fillets. Use this when you want the export geometry to match the original model.

The control starts at **1 mm each time you open the part picker**. It applies to this export only and does not change the source model or saved panel tags. Removed fillets are omitted from **all export copies**, including DXFs, STEP files, `Flat_parts.FCStd` and the sheet preview. Existing exports are not changed; run a new export to apply the setting.

Fillet removal follows native **PartDesign Fillet** features in the model's history. Small holes, slots and other curves are not selected just because of their radius. Mirrored copies of whole parts are supported when their references lead back to that history. Holes and pockets added after a fillet must survive the geometry checks.

**Imported STEP parts and other solids without native fillet history keep their fillets.** The sheet-settings window reports how many parts had fillets removed and how many lacked that history. Detailed results are saved in each part's `fillet_removal` entry in `manifest.json`.

If a selected fillet cannot be removed safely, the export stops and names the part. Adjust the cutoff, correct the model, or leave that part out. Setting the cutoff to 0 keeps the original fillets, but does not bypass the exporter's normal geometry checks.

### 2. Set up the sheets

Use **Browse…** beside **Export folder** to choose where to save the files. The tool creates a new folder there for each export, keeping previous exports.

Review the part settings:

| Setting | What to do |
| --- | --- |
| Quantity | Leave at **1** for one copy of that row. Each placed assembly instance has its own row. A quantity of **2** makes two copies of that row; **0** leaves it out. |
| Rotation | Choose how the part lies on the sheet: 0°, 90°, 180° or 270°. The tool will not rotate it automatically to make it fit. |
| Grain | If grain matters, specify its direction along the first or second dimension shown for the unrotated part. It must line up with the sheet grain after rotation. |
| Flip | Turn the part over if you want the opposite face uppermost. By default, the face with the most recesses faces up. |

Below the parts, there is a sheet-settings section for each detected thickness. Enter your actual **sheet length and width**, **sheet edge margin**, **gap between machining outlines** and **sheet grain**. All dimensions are in **millimetres**. The default sheet size is 2440 × 1220 mm; check it against your stock.

Leave **Extend open rebates past edges** at **0 mm** unless you need that feature. It extends the drawing of an edge-opening recess beyond the part edge for machining. The per-part checkbox lets you exclude a part from this setting.

Different thicknesses use separate sheets. Parts of the **same thickness are treated as the same material**, so export different materials separately. The tool measures thickness from the model; it never resizes a part to match your stock.

### 3. Preview and export

Review the sheet preview. It updates automatically unless you turn that option off; you can also click **Update sheet preview**. Adjust the settings if the layout reports a problem.

If needed, change operation-layer colours or double-click a layer name below the preview to rename it. Renaming a layer does not change the operation's depth.

Click **Export sheet DXFs…**. When the export finishes, click **Open export folder**. If the option to save and open a sheet layout is checked, the tool also opens a separate FreeCAD layout document.

**Start with the `Sheet_*.dxf` files in your CAM software**, and read `SHEET_NOTES.txt` before setting up machining.

## What is in the export folder?

| File | What it is for |
| --- | --- |
| `Sheet_*.dxf` | The arranged sheet drawings, showing the upper machining face. |
| Individual part `.dxf` files | Drawings of each exported part on its own. |
| Individual part `.step` files | 3D export solids, including features on both sides and the chosen fillet-removal setting. |
| `Flat_parts.FCStd` | A FreeCAD document containing the flattened 3D parts. |
| `Sheet_layout.FCStd` | An optional FreeCAD sheet-layout preview. |
| `parts.csv` and `quantities.csv` | Part dimensions, sheet placements and quantities; open these in a spreadsheet. |
| `SHEET_NOTES.txt` | Machining notes and explanations of reference layers. |
| `manifest.json` | Detailed export records, including operation depths, underside features and fillet-removal results. |

## Optional: remember which parts are panels

Use **Panel Tags** when you expect to export from the same model again. A tag tells the export picker to start with that component checked.

1. Select parts or a complete cabinet/assembly, then click **Panel Tags**. An assembly selection expands into its individual components.
2. Check the panels, leave fittings unchecked, and click **Save panel tags**. Use search and **Check shown / Uncheck shown** for longer lists. Unchecking a previously tagged component removes its tag.
3. Save the model as a FreeCAD **`.FCStd` file** to keep the tags. STEP files do not store them.

Tags only add information to the model; they do not change its shape. Tag changes can be undone. Leaving a part out of one export does not remove its saved tag.

In either selection dialog, searching only hides rows: **checked rows remain checked even when hidden by a search**. Check the selection count before continuing.

## Limits to understand before machining

- **Only the chosen upper face is drawn for machining.** Underside operations are recorded in the notes and `manifest.json`, and remain in the exact 3D files. No separate underside sheet layout is generated. Plan the second setup in CAM if your part needs one.
- **Sheet layout uses rectangular packing.** It leaves room around each part's machining boundaries. It does not nest irregular shapes together or guarantee the best material yield.
- **Drawings are not finished toolpaths.** Reference layers and labels are not cuts. Taper and roundover guides still need cutter and toolpath setup in CAM.
- **Fillet removal needs identifiable model history.** It supports native PartDesign fillets and verified whole-part references and Part mirrors. Imported solids, partial references and other modelling patterns are not automatically simplified. A copy with additional unaccounted geometry changes is rejected rather than losing those changes.
- **Geometry support has limits.** Parts need valid solids with a broad flat face. Supported features include flat-bottomed recesses, perpendicular holes and drill tips, supported tapers and convex edge roundovers, with straight or circular-arc boundaries. Sideways or angled drilling, freeform boundaries and ambiguous thickness can stop an export.

## Troubleshooting

| Problem | What to try |
| --- | --- |
| The installer says the folder is incomplete | Extract the complete ZIP and select the folder containing all three macros and both icons. |
| The toolbar does not appear | Finish any active edit, then switch workbenches or restart FreeCAD. If installation failed, try the manual steps above. |
| The parts I expected are not checked | Check them manually. Tags and individually selected parts start checked; untagged children of a selected assembly do not. |
| Rounded corners remain in the export | Check **Remove fillets up to** in the part picker. The radius is inclusive; larger fillets remain. Imported solids without native fillet history are not simplified. Generate a new export after changing the setting. |
| I want to keep the model's fillets | Set **Remove fillets up to** to **0 — Off** before continuing. It defaults to 1 mm when the part picker opens again. |
| Fillet removal fails on a part | Read the named part and reason. Reduce the cutoff or set it to 0 to retain its fillets, correct the model, or uncheck the part. Keeping fillets does not make otherwise unsupported geometry exportable. |
| A selected part stops the export | Read the named part and reason in the error message. Correct it, or run the tool again and uncheck that part to export the others. |
| Thickness cannot be detected reliably | Try selecting a broad flat face on the part before running the tool. This can guide flattening. |
| A part will not fit, or grain does not line up | Check its rotation, sheet dimensions, margins, gap and grain settings, then update the preview. |
| A linked array cannot be exported | Expand it into individual component links first. The tool does not guess array quantities. |
| The tool says this is an export preview | Switch back to your original model's document tab and run it there. |
| An unexpected error occurs | Open **View → Panels → Report View** for details. |

<details>
<summary>Advanced: how tags work with shared and linked components</summary>

The saved Boolean property is `LayFlatPanel`, in the **Lay Flat for CNC** group of a component's Data properties.

- Shared placements of a component use the same tag, but the export picker counts each placed instance separately.
- A component containing multiple solids has one tag for all of them. Use separate component objects if you need separate saved tags.
- A local component's tag overrides its linked source's tag, including an explicit `False`. Otherwise, links can inherit source tags.
- Panel Tags does not automatically edit external source documents. External child components are read-only in the tagging list. Tag a local component link, or open the source document to tag its definition.
- Unselected unsupported solids do not need to pass machining checks, but unresolved links and structural assembly errors still need to be repaired.

</details>
