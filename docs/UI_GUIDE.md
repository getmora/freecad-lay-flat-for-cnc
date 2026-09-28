# Screenshot walkthrough

This guide explains **how to open each screen, why you would use it, and what to click next**. The screenshots show FreeCAD Lay Flat for CNC 0.12.8 on FreeCAD 1.1.3 for macOS, using an example cabinet. They are not separate panels you need to enable individually.

## Start here: make the two toolbar buttons available

1. Download and extract the complete ZIP from the [main README](../README.md#install). In FreeCAD, use **File → Open** to open `Install_FreeCAD_Lay_Flat_for_CNC.FCMacro` from that extracted folder.
2. Click inside the installer’s editor tab, then choose **Macro → Execute macro**. If a folder chooser appears, choose the extracted download folder. This installs the files and creates the **FreeCAD Lay Flat for CNC** toolbar.
3. Look for that toolbar. If it is hidden, open **View → Toolbars** and tick **FreeCAD Lay Flat for CNC**. If it is not listed, finish any active model edit and switch workbenches or restart FreeCAD after saving your work. Check that the installer completed successfully.

The two buttons do different jobs:

| Button | Why use it? | What to do before clicking |
| --- | --- | --- |
| <img src="../panel-tags.svg" width="28" alt="Panel Tags icon"> **Panel Tags** | Optional: remember which components are panels so they start checked next time. Opens **image 1**. | Open your original model and select a part, cabinet or assembly in its model tree. |
| <img src="../lay-flat-for-cnc.svg" width="28" alt="Lay Flat for CNC icon"> **Lay Flat for CNC** | Start selecting parts and arranging a sheet layout. Opens **image 2**. | Open your original model. Select parts/an assembly, or clear the selection to consider the visible model. |

Hover over an icon to see its tooltip. **Panel Tags is not required before Lay Flat:** skip directly to [image 2](#2-choose-parts-and-the-fillet-cutoff) for a one-off layout.

**No toolbar buttons?** You can still run the tools through **Macro → Macros…**: select `Panel_Tags.FCMacro` or `FreeCAD_Lay_Flat_for_CNC.FCMacro`, then click **Execute**. Copying files manually makes the macros available but does not create the two custom toolbar buttons; run the installer to create those buttons.

**“Execute macro” is greyed out while installing?** That command runs the macro in the active editor tab. Open the installer file and click inside its editor first. This is different from **Macro → Macros…**, which lets you choose an installed macro from a list.

## 1. Optional panel tags

**Why use this screen?** Use it when you will export the same model again and want the tool to remember which components are plywood panels. It marks your choices in the model; it does not flatten anything, create a sheet layout or export files.

**How to open it:** open the original model, select a part or whole cabinet/assembly in the model tree, then click the **Panel Tags** toolbar button. Selecting a whole assembly lists the parts inside it.

1. Check the components that should count as panels. Leave hinges, screws and other fittings unchecked. Use the search box to find a part; **Check shown / Uncheck shown** affects only the rows currently shown by the filter.
2. Click **Save panel tags** to apply your changes. That button becomes available only when a checkbox differs from the saved choice. In the screenshot, **Base panel** is checked but its current tag says **Not tagged**, so there is one change ready to save. **Cancel** closes the screen without saving the checkbox changes.
3. Save the original model as an **`.FCStd` file** to keep the tags. Then click **Lay Flat for CNC** to start the layout. The tagged panels will start checked in the next screen.

Previously tagged components can be untagged by unchecking them and saving. Greyed-out rows belong to an external source model; open that source model to edit those tags.

![Panel Tags dialog with four panels checked and a support block excluded](images/01-panel-tags.png)

## 2. Choose parts and the fillet cutoff

**Why use this screen?** Decide exactly which placed parts belong in this layout and whether small finishing fillets should be removed from its manufacturing copies.

**How to open it:** click the **Lay Flat for CNC** toolbar button while your original model is active. A selected cabinet/assembly lists its contents; selecting individual parts prechecks them. With no selection, the tool considers the visible model. An untagged assembly’s contents are not all checked automatically.

1. Check the parts you want. Click a row to highlight its source component. **Select tagged panels** checks the saved panel choices; **Select shown** checks the filtered rows; **Clear all** unchecks everything. Search only hides rows—it does not uncheck hidden selections.
2. Set **Remove fillets up to** if needed. It starts at **1 mm**, including exactly 1 mm. Set **0 — Off** to keep all fillets. This affects export copies, not the original model, and does not remove arbitrary small holes or curves.
3. Click **Continue** to open the sheet settings in image 3. **Cancel** stops here without creating a layout or exporting files. Changing these checkboxes does not change your saved panel tags.

![Part picker showing the selected panels and adjustable 1 mm fillet cutoff](images/02-select-parts.png)

## 3. Set up and preview the sheets

**Why use this screen?** Fit the selected parts onto your actual stock before creating the layout document.

**How to open it:** choose your parts in image 2 and click **Continue**.

1. Set each part’s quantity, rotation and grain requirements. A quantity of **0** leaves it out. **Flip over** changes which face is uppermost. Enter the sheet size, margin and spacing for each thickness; the example’s sizes are not stock recommendations.
2. Inspect the preview. **Automatically update preview** refreshes it after changes; **Update sheet preview** refreshes it manually. Below the preview, click a **Choose…** colour button to change a layer’s colour, or double-click its layer name to rename it. Scroll down if that table is below the visible area.
3. Click **Create sheet layout** to open the generated document in images 4–5. **No DXF, SVG, STEP or part-list files are exported yet.** **Cancel** closes the settings without creating that document.

![Sheet settings and preview with separate 6 mm and 18 mm stock](images/03-sheet-settings.png)

## 4. Inspect the layout

**Why use this view?** Check the arrangement and machining outlines before choosing an export format.

**How to open it:** click **Create sheet layout** in image 3. FreeCAD opens and activates a new **Sheet layout** document, with a top view of the sheets.

The colours distinguish operations. Different thicknesses stay on separate sheets. This screenshot shows the drawing area; use the model tree in image 5 to select or inspect an operation.

Save this layout using FreeCAD’s normal **File → Save** if you want to reopen it later. To change part selection, quantities or geometry, return to the original model and create a new layout; directly editing the generated machining geometry will cause export validation to stop.

![FreeCAD top view of the two example sheets](images/04-sheet-layout.png)

## 5. Read the operation tree

**Why use this tree?** Find all matching cuts together rather than searching through every individual part.

**How to open it:** in the generated layout’s model tree, click the expansion arrow beside **Sheet layouts — operations**, then beside a sheet.

1. Click an operation such as **Holes — diameter 5 mm — depth 12 mm** to highlight that operation’s geometry across the sheet. Select its **Data** properties to see the exact DXF layer, feature count and contributing part numbers/names.
2. Expand **Guides — not cuts** only when you need sheet boundaries, margins, part labels or other reference geometry. The **3D copies — reference only** group is initially hidden and is separate from the cutting outlines.
3. Right-click **Sheet layouts — operations**, or an individual sheet, when ready to export. This opens the action shown in image 6.

**UP** means the upward-facing machining setup. **(Sheet 1)** identifies the sheet; it is not a diameter or cutting depth.

![Model tree showing outside profiles, a 6 mm pocket, 5 mm holes and 35 mm holes grouped by operation](images/05-operation-tree.png)

## 6. Export from the tree

**Why use this action?** Export only after inspecting the layout, and choose whether to export all sheets or one.

**How to open it:** right-click the **Sheet layouts — operations** row in the generated document’s model tree. Choose **Export all sheets…**. To export one sheet, right-click that sheet’s row instead and choose **Export this sheet…**.

Clicking the action opens the export dialog in image 7; it does not immediately save files. The screenshot shows the action added by this macro. FreeCAD may also show its standard context-menu actions.

If an older layout has no export action, activate that layout and run **Lay Flat for CNC** once to enable sheet-only exports. Newly created layouts restore their actions after reopening when the complete macro package is installed.

![Export all sheets context-menu action](images/06-export-menu.png)

## 7. Choose the destination and package contents

**Why use this screen?** Decide what files to create and where they should go.

**How to open it:** choose **Export all sheets…** or **Export this sheet…** from image 6.

1. Open the **Format** dropdown and choose a format from image 8. Click **Browse…** to select an existing destination folder.
2. For all sheets from a newly created layout, keep **Include individual parts, STEP files and part lists** checked for the complete package. Uncheck it for sheet drawings and notes only. It is unavailable for single-sheet exports or older layouts without individual-part export data; create a new layout from the original model if you need that package.
3. Click **Export** to write the files. This is the point where file export happens. **Cancel** closes the dialog without exporting. Each export gets a new folder, so previous exports are kept.

The completion message gives the saved location. **Open export folder** opens it in your computer’s file manager; **OK** closes the message.

![Export dialog with DXF and SVG selected and the complete package enabled](images/07-export-options.png)

## 8. Choose an export format

**Why use this control?** Select the drawing format your CAM or vector software expects.

**How to open it:** click the arrow at the right of **Format** in image 7.

| Choice | What it produces |
| --- | --- |
| **DXF** | Standard R2004 DXF drawings. |
| **SVG** | SVG drawings in millimetres at 1:1 scale, with named operation groups. |
| **DXF and SVG** | Both drawing formats in the same export folder. |
| **Mozaik — R12 DXF** | Older R12 DXF using closed polylines; see image 9 before importing. |

Choosing an option only changes the export settings. You still need to click **Export** in image 7 to create files.

![Format choices: DXF, SVG, DXF and SVG, and Mozaik R12 DXF](images/08-export-formats.png)

## 9. Use the Mozaik preset

**Why use this option?** Mozaik’s documented custom-part import expects R12 closed polylines. This preset targets that format; it does not create Mozaik toolpaths or automatically assign tools.

**How to open it:** in image 7’s **Format** dropdown, choose **Mozaik — R12 DXF**. The extra instructions then appear in the dialog.

1. For individual-part import, use **Export all sheets…** and keep the complete-package checkbox checked. If it is unavailable, create a new layout from the original model first.
2. Click **Export**, then open the saved folder. Use the **individual-part `_R12.dxf` files**, not the nested `Sheet_*` drawings. The preset omits reference borders, guides and labels from the R12 drawings.
3. Select **millimetres** when importing into Mozaik, and assign the machining tools there. `R12_LAYERS.csv` explains any shortened layer names.

An independent DXF reader checked the R12 structure and geometry. **Actual import into Mozaik remains unverified.**

![Mozaik R12 export option and its import instructions](images/09-mozaik-r12.png)

[Return to the main README](../README.md)
