"""Persistent sheet-layout menus and millimetre SVG export for Lay Flat."""
from pathlib import Path
from datetime import datetime
import json
import csv
import math
import re
import runpy
import shutil
import tempfile
import traceback
import xml.etree.ElementTree as ET

import FreeCAD as App
import Part

_CORE = None
_CORE_STAMP = None
SVG_NS = 'http://www.w3.org/2000/svg'
INKSCAPE_NS = 'http://www.inkscape.org/namespaces/inkscape'
ET.register_namespace('', SVG_NS)
ET.register_namespace('inkscape', INKSCAPE_NS)
FORMAT_CHOICES = (
    ('DXF', ('dxf',)),
    ('SVG', ('svg',)),
    ('DXF and SVG', ('dxf', 'svg')),
    ('Mozaik — R12 DXF', ('dxf_r12',)),
)
SUPPORTED_FORMATS = frozenset(fmt for _, formats in FORMAT_CHOICES for fmt in formats)


def core(path=None):
    global _CORE, _CORE_STAMP
    path = Path(path).resolve() if path is not None else Path(__file__).with_name('FreeCAD_Lay_Flat_for_CNC.FCMacro')
    if not path.is_file():
        raise RuntimeError('Lay Flat is incomplete. Reinstall the complete macro package to export this layout.')
    stat = path.stat()
    stamp = (str(path), stat.st_mtime_ns, stat.st_size)
    if _CORE is None or stamp != _CORE_STAMP:
        _CORE = runpy.run_path(str(path), run_name='lay_flat_export_runtime')
        _CORE_STAMP = stamp
    return _CORE


def number(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('Export geometry contains a non-finite coordinate.')
    return ('%.12f' % value).rstrip('0').rstrip('.') or '0'


def validate_formats(formats):
    try:
        formats = tuple(dict.fromkeys(formats))
    except TypeError as exc:
        raise ValueError('Choose DXF, SVG, both, or Mozaik R12 DXF.') from exc
    if not formats or any(fmt not in SUPPORTED_FORMATS for fmt in formats):
        raise ValueError('Choose DXF, SVG, both, or Mozaik R12 DXF.')
    return formats


def closed_polyline_vertices(tags):
    """One validated interpretation of the DXF vertices shared by SVG/R12."""
    if not dict(tags).get(70, 0) & 1:
        raise ValueError('A cutting polyline must be a closed outline.')
    vertices = []
    for code, value in tags:
        if code == 10:vertices.append([float(value), None, 0.0])
        elif code == 20 and vertices:vertices[-1][1] = float(value)
        elif code == 42 and vertices:vertices[-1][2] = float(value)
    if len(vertices) < 2 or any(v[1] is None for v in vertices):
        raise ValueError('A cutting outline has incomplete vertices.')
    if not all(math.isfinite(value) for vertex in vertices for value in vertex):
        raise ValueError('Export geometry contains a non-finite coordinate.')
    return vertices


def save_svg(drawing, path, width, height, bounds=None):
    """Convert the exact DXF primitives, including arc bulges, to SVG layers."""
    dx, dy = 0.0, 0.0
    if bounds is not None:
        dx, dy, xmax, ymax = bounds
        width, height = xmax-dx, ymax-dy
    def x(value):return number(value-dx)
    def y(value):return number(height-(value-dy))
    if width <= 0 or height <= 0:
        raise ValueError('SVG dimensions must be positive.')
    root = ET.Element('{%s}svg' % SVG_NS, {'version': '1.1', 'width': number(width)+'mm',
        'height': number(height)+'mm', 'viewBox': '0 0 %s %s' % (number(width), number(height))})
    ET.SubElement(root, '{%s}desc' % SVG_NS).text = 'Millimetres, 1:1. Named operation layers are geometry for CAM, not toolpaths. REFERENCE and LABELS layers are not cuts.'
    groups = {}
    palette = drawing.palette or core()['make_layer_palette'](drawing.layers)
    for tags in drawing.entities:
        values = dict(tags)
        kind, layer = values[0], values.get(8, '0')
        if layer not in palette:
            raise ValueError('No colour assigned for layer '+layer)
        if layer not in groups:
            group = ET.SubElement(root, '{%s}g' % SVG_NS, {'id':'layer_%d' % len(groups),
                '{%s}groupmode' % INKSCAPE_NS:'layer', '{%s}label' % INKSCAPE_NS:layer,
                'data-layer':layer, 'fill':'none', 'stroke':palette[layer]['hex'], 'stroke-width':'0.1'})
            ET.SubElement(group, '{%s}title' % SVG_NS).text = layer
            groups[layer] = group
        group = groups[layer]
        if kind == 'CIRCLE':
            ET.SubElement(group, '{%s}circle' % SVG_NS, {'cx':x(values[10]),
                'cy':y(values[20]), 'r':number(values[40])})
        elif kind == 'LINE':
            ET.SubElement(group, '{%s}line' % SVG_NS, {'x1':x(values[10]), 'y1':y(values[20]),
                'x2':x(values[11]), 'y2':y(values[21])})
        elif kind == 'TEXT':
            # Sheet titles outside the stock belong in metadata, not an
            # enlarged SVG page that changes the physical sheet dimensions.
            if not (dx <= values[10] <= dx+width and dy <= values[20] <= dy+height):
                continue
            text = ET.SubElement(group, '{%s}text' % SVG_NS, {'x':x(values[10]),
                'y':y(values[20]), 'font-size':number(values[40]),
                'fill':palette[layer]['hex'], 'stroke':'none'})
            text.text = str(values[1])
        elif kind == 'LWPOLYLINE':
            vertices = closed_polyline_vertices(tags)
            commands = ['M %s %s' % (x(vertices[0][0]), y(vertices[0][1]))]
            for i, (vx, vy, bulge) in enumerate(vertices):
                nx, ny, _ = vertices[(i+1) % len(vertices)]
                if abs(bulge) < 1e-14:
                    commands.append('L %s %s' % (x(nx), y(ny)))
                else:
                    radius = math.hypot(nx-vx, ny-vy)*(1+bulge*bulge)/(4*abs(bulge))
                    if radius <= 0:raise ValueError('Degenerate SVG circular arc.')
                    commands.append('A %s %s 0 %d %d %s %s' % (number(radius), number(radius),
                        int(abs(4*math.atan(bulge)) > math.pi), int(bulge < 0), x(nx), y(ny)))
            commands.append('Z')
            ET.SubElement(group, '{%s}path' % SVG_NS, {'d':' '.join(commands)})
        else:
            raise ValueError('Unsupported SVG entity: '+str(kind))
    ET.ElementTree(root).write(str(path), encoding='utf-8', xml_declaration=True)


def is_reference_layer(layer, palette):
    source = palette.get(layer, {}).get('source_layer', layer)
    return layer in ('0', 'LABELS') or layer.startswith('REFERENCE_') or source.startswith('REFERENCE_')


def r12_layer_names(palette):
    """R12 symbol names are limited to 31 characters; keep a reversible map."""
    result, used = {}, set()
    sources = sorted(name for name in palette if not is_reference_layer(name, palette))
    for index, original in enumerate(sources, 1):
        name = original.upper().replace('_DEPTH_', '_DEPTH').replace('_TIP_', '_TIP').replace('MM_TIP', '_TIP')
        name = re.sub(r'[^A-Z0-9_$-]', '_', name).strip('_')
        if not name or len(name) > 31 or name in used or name.startswith('OPERATION_'):
            name = 'OPERATION_%02d' % index
        while name in used:name += '_'
        if len(name) > 31:raise ValueError('Cannot assign an unambiguous R12 layer name.')
        used.add(name);result[original] = name
    return result


def save_r12(drawing, path):
    """Mozaik-targeted AC1009: closed 2D POLYLINE/VERTEX chains only."""
    palette = drawing.palette or core()['make_layer_palette'](drawing.layers)
    names = r12_layer_names(palette)
    polylines = []
    for tags in drawing.entities:
        values = dict(tags)
        layer = values.get(8, '0')
        if is_reference_layer(layer, palette):continue
        if layer not in names:raise ValueError('No R12 colour/layer definition for '+layer)
        kind = values.get(0)
        if kind == 'CIRCLE':
            cx, cy, radius = float(values[10]), float(values[20]), float(values[40])
            if not math.isfinite(radius) or radius <= 0:raise ValueError('Invalid circular hole radius.')
            bulge = math.tan(math.pi/8)
            vertices = [(cx+radius,cy,bulge), (cx,cy+radius,bulge),
                        (cx-radius,cy,bulge), (cx,cy-radius,bulge)]
        elif kind == 'LWPOLYLINE':
            vertices = closed_polyline_vertices(tags)
        else:
            raise ValueError('The Mozaik preset cannot export %s on cutting layer %s; a closed outline is required.' % (kind,layer))
        for vertex in vertices:
            for value in vertex:number(value)  # Reject NaN/infinity before writing.
        polylines.append((layer,vertices))
    if not polylines:raise ValueError('No closed cutting outlines were found for the Mozaik preset.')
    used = sorted({layer for layer,_ in polylines})
    tags = [(0,'SECTION'),(2,'HEADER'),(9,'$ACADVER'),(1,'AC1009'),
            (9,'$LUNITS'),(70,2),(9,'$LUPREC'),(70,6),
            (9,'$INSBASE'),(10,0.0),(20,0.0),(30,0.0),(0,'ENDSEC'),
            (0,'SECTION'),(2,'TABLES'),(0,'TABLE'),(2,'LTYPE'),(70,1),
            (0,'LTYPE'),(2,'CONTINUOUS'),(70,0),(3,'Solid line'),(72,65),(73,0),(40,0.0),(0,'ENDTAB'),
            (0,'TABLE'),(2,'LAYER'),(70,len(used)+1),
            (0,'LAYER'),(2,'0'),(70,0),(62,7),(6,'CONTINUOUS')]
    for layer in used:
        colour = int(palette[layer]['aci'])
        if not 1 <= colour <= 255:raise ValueError('Invalid R12 indexed colour for '+layer)
        tags += [(0,'LAYER'),(2,names[layer]),(70,0),(62,colour),(6,'CONTINUOUS')]
    tags += [(0,'ENDTAB'),(0,'ENDSEC'),(0,'SECTION'),(2,'ENTITIES')]
    for layer, vertices in polylines:
        name = names[layer]
        tags += [(0,'POLYLINE'),(8,name),(66,1),(10,0.0),(20,0.0),(30,0.0),(70,1)]
        for x,y,bulge in vertices:
            tags += [(0,'VERTEX'),(8,name),(10,x),(20,y),(30,0.0),(70,0)]
            if bulge:tags.append((42,bulge))
        tags += [(0,'SEQEND'),(8,name)]
    tags += [(0,'ENDSEC'),(0,'EOF')]
    with open(path,'w',encoding='ascii',newline='\n') as stream:
        handle = 0x100
        for code,value in tags:
            stream.write('%d\n%s\n' % (code, number(value) if isinstance(value,float) else value))
            if code == 0 and value in ('LTYPE','LAYER','POLYLINE','VERTEX','SEQEND'):
                stream.write('5\n%X\n' % handle);handle += 1


def write_r12_layer_guide(folder, palette):
    with open(Path(folder)/'R12_LAYERS.csv', 'w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream);writer.writerow(['R12 layer', 'Original operation layer'])
        writer.writerows((short, original) for original, short in r12_layer_names(palette).items())


def write_drawing(drawing, folder, basename, formats, width, height, bounds=None):
    names = []
    for fmt in validate_formats(formats):
        name = basename+'_R12.dxf' if fmt == 'dxf_r12' else basename+'.'+fmt
        if fmt == 'dxf':drawing.save(Path(folder)/name)
        elif fmt == 'dxf_r12':save_r12(drawing, Path(folder)/name)
        else:save_svg(drawing, Path(folder)/name, width, height, bounds)
        names.append(name)
    return names


def encode_part(part):
    result = {k:v for k,v in part.items() if not k.startswith('_') and k not in ('shape','operations','underside_operations')}
    result['shape_brep'] = part['shape'].exportBrepToString()
    for key in ('operations', 'underside_operations'):
        result[key] = [dict({k:v for k,v in op.items() if k != 'face'}, face_brep=op['face'].exportBrepToString())
                       for op in part.get(key, [])]
    return result


def decode_part(data):
    part = dict(data)
    shape = Part.Shape();shape.importBrepFromString(part.pop('shape_brep'), False)
    if not shape.isValid() or len(shape.Solids) != 1:raise ValueError('Saved layout has an invalid part solid.')
    part['shape'] = shape
    for key in ('operations', 'underside_operations'):
        part[key] = []
        for stored in data[key]:
            op = dict(stored)
            face = Part.Shape();face.importBrepFromString(op.pop('face_brep'), False)
            if len(face.Faces) != 1:raise ValueError('Saved operation is not one face.')
            op['face'] = face.Faces[0];part[key].append(op)
    return part


def add_property(obj, kind, name, value):
    if name not in obj.PropertiesList:obj.addProperty(kind, name, 'Lay Flat export')
    setattr(obj, name, value)
    obj.setEditorMode(name, 1)


def bind_layout(doc, root, sheet_objects, sheets, settings, palette, namespace, title):
    indexed = {p['part_index']:p['part'] for sheet in sheets for p in sheet['placements']}
    if sorted(indexed) != list(range(1, len(indexed)+1)):
        raise ValueError('Layout part numbers are incomplete.')
    payload = {'schema':1, 'title':title, 'settings':settings, 'palette':palette,
               'parts':[encode_part(indexed[i]) for i in sorted(indexed)], 'sheets':[], 'objects':[]}
    for obj, sheet in zip(sheet_objects, sheets):
        drawing = namespace['sheet_drawing'](sheet, 'FRONT', settings, palette)
        payload['sheets'].append(dict(index=sheet['index'], width_mm=sheet['width_mm'], height_mm=sheet['height_mm'],
            thickness_mm=sheet['thickness_mm'], placements=[{k:v for k,v in p.items() if k!='part'} for p in sheet['placements']],
            entities=drawing.entities, layers=drawing.layers))
        add_property(obj, 'App::PropertyInteger', 'SheetNumber', sheet['index'])
        add_property(obj, 'App::PropertyLink', 'LayoutRoot', root)
        if App.GuiUp:SheetLayoutViewProvider(obj.ViewObject)
    for obj in doc.Objects:
        if 'DxfLayer' in obj.PropertiesList:
            payload['objects'].append(dict(name=obj.Name, layer=obj.DxfLayer, brep=obj.Shape.exportBrepToString()))
    add_property(root, 'App::PropertyString', 'ExportPayload', json.dumps(payload, ensure_ascii=False))
    add_property(root, 'App::PropertyInteger', 'LayoutSchema', 1)
    if App.GuiUp:SheetLayoutViewProvider(root.ViewObject)


def validate_layout(root, payload):
    if payload.get('schema') != 1:raise ValueError('This layout version is not supported. Create a new layout.')
    expected_names = {item['name'] for item in payload['objects']}
    actual_names = {obj.Name for obj in root.Document.Objects if 'DxfLayer' in obj.PropertiesList}
    if actual_names != expected_names:raise ValueError('The layout operations have changed. Undo the edits or create a new layout before exporting.')
    for record in payload['objects']:
        obj = root.Document.getObject(record['name'])
        if obj is None or obj.DxfLayer != record['layer']:raise ValueError('The saved operation layers have changed. Create a new layout.')
        actual = obj.Shape
        if actual.exportBrepToString() == record['brep']:
            continue  # Exact equality is stronger and cheaper than boolean cuts.
        expected = Part.Shape();expected.importBrepFromString(record['brep'], False)
        tolerance = max(1e-5, expected.Length*1e-9)
        if (abs(actual.Length-expected.Length) > tolerance or len(actual.Edges) != len(expected.Edges)
                or actual.cut(expected).Length+expected.cut(actual).Length > tolerance):
            raise ValueError('Layout geometry was edited after creation. Undo the edits or create a new layout; no files were exported.')


def upgrade_legacy_layout(doc):
    """Enable drawing exports on an older layout using its existing geometry."""
    root = doc.getObject('SheetLayouts')
    if root is None:raise ValueError('No sheet layout was found in this document.')
    if 'ExportPayload' in root.PropertiesList:return root
    namespace = core()
    def descendants(group):
        result, stack, seen = [], list(group.Group), set()
        while stack:
            obj = stack.pop(0)
            if obj.Name in seen:continue
            seen.add(obj.Name);result.append(obj)
            stack.extend(getattr(obj, 'Group', []))
        return result
    layers = [obj.DxfLayer for obj in doc.Objects if 'DxfLayer' in obj.PropertiesList]
    palette = namespace['make_layer_palette'](layers)
    for obj in doc.Objects:
        if 'DxfLayer' in obj.PropertiesList and App.GuiUp:
            colour = '#'+''.join('%02x' % round(channel*255) for channel in obj.ViewObject.LineColor)
            palette[obj.DxfLayer] = dict(hex=colour, aci=namespace['nearest_aci'](colour), true_colour=int(colour[1:],16))
    payload = dict(schema=1, title='Sheet layout', palette=palette, settings={}, parts=None, sheets=[], objects=[])
    groups = list(root.Group)
    for group in groups:
        match = re.fullmatch(r'Sheet (\d+) — UP — ([\d.]+) mm', group.Label)
        if match is None:raise ValueError('This older layout has an unrecognised sheet description. Create a new layout from the source model.')
        index, thickness = int(match[1]), float(match[2])
        children = descendants(group)
        boundary = next((obj for obj in children if obj.Name.startswith('SheetBoundary')), None)
        if boundary is None:raise ValueError('A sheet boundary is missing; its physical size cannot be verified.')
        box = boundary.Shape.BoundBox
        drawing = namespace['Dxf'](palette)
        for obj in children:
            if 'DxfLayer' in obj.PropertiesList:
                payload['objects'].append(dict(name=obj.Name, layer=obj.DxfLayer, brep=obj.Shape.exportBrepToString()))
                layer = obj.DxfLayer
            elif obj.Name.startswith('SheetBoundary'):layer = 'REFERENCE_SHEET'
            elif obj.Name.startswith('SheetMargin'):layer = 'REFERENCE_MARGIN'
            else:layer = None
            if layer:
                for wire in obj.Shape.Wires:
                    copy = wire.copy();copy.translate(App.Vector(-box.XMin,-box.YMin,0))
                    drawing.add_wire(copy, layer)
            elif obj.Name.startswith('GrainDirection'):
                for edge in obj.Shape.Edges:
                    a,b = edge.Vertexes[0].Point,edge.Vertexes[-1].Point
                    drawing.add_line((a.x-box.XMin,a.y-box.YMin),(b.x-box.XMin,b.y-box.YMin))
            elif obj.TypeId == 'App::Annotation':
                drawing.add_text(' '.join(obj.LabelText), obj.Position.x-box.XMin, obj.Position.y-box.YMin,
                                 obj.ViewObject.FontSize if App.GuiUp else 5)
        payload['sheets'].append(dict(index=index, width_mm=box.XLength, height_mm=box.YLength,
            thickness_mm=thickness, entities=drawing.entities, layers=drawing.layers))
    # Complete validation precedes document mutation; the transaction rolls
    # back grouping changes if attaching a persistent view provider fails.
    encoded = json.dumps(payload, ensure_ascii=False)
    state = [(group.Name, group.Label, list(group.Group), group.ViewObject.Visibility if App.GuiUp else True) for group in groups]
    root_name, root_label = root.Name, root.Label
    visible = {obj.Name:obj.ViewObject.Visibility for obj in doc.Objects} if App.GuiUp else {}
    doc.openTransaction('Enable sheet layout export')
    try:
        for group in groups:doc.removeObject(group.Name)
        doc.removeObject(root_name)
        root = doc.addObject('App::DocumentObjectGroupPython', root_name);root.Label = root_label
        add_property(root,'App::PropertyString','ExportPayload',encoded)
        add_property(root,'App::PropertyInteger','LayoutSchema',1)
        if App.GuiUp:SheetLayoutViewProvider(root.ViewObject)
        for (name,label,children,is_visible), sheet in zip(state,payload['sheets']):
            obj = doc.addObject('App::DocumentObjectGroupPython',name);obj.Label=label;obj.Group=children
            root.addObject(obj)
            add_property(obj,'App::PropertyInteger','SheetNumber',sheet['index'])
            add_property(obj,'App::PropertyLink','LayoutRoot',root)
            if App.GuiUp:SheetLayoutViewProvider(obj.ViewObject)
        doc.recompute()
        if App.GuiUp:
            for name,value in visible.items():
                obj=doc.getObject(name)
                if obj is not None:obj.ViewObject.Visibility=value
        doc.commitTransaction()
        return root
    except Exception:
        doc.abortTransaction()
        raise


def export_layout(obj, parent, formats=('dxf',), include_package=False):
    formats = validate_formats(formats)
    root = obj if 'ExportPayload' in obj.PropertiesList else obj.LayoutRoot
    if root is None:raise ValueError('The layout export data is missing.')
    payload = json.loads(root.ExportPayload)
    validate_layout(root, payload)
    namespace = core()
    selected = getattr(obj, 'SheetNumber', None)
    sheets = [s for s in payload['sheets'] if selected is None or s['index']==selected]
    if not sheets:raise ValueError('The selected sheet is missing from the saved layout.')
    parent = Path(parent).expanduser()
    if not parent.is_dir():raise ValueError('Choose an existing export folder.')
    if include_package:
        if selected is not None or not payload.get('parts'):
            raise ValueError('The complete package is available only from all sheets in a newly created layout.')
        parts = [decode_part(data) for data in payload['parts']]
        return namespace['output_parts'](parts, parent, payload['title'], True, payload['settings'],
                                         drawing_formats=formats, expected_layout=payload['sheets'])
    staging = Path(tempfile.mkdtemp(prefix='.lay-flat-export-', dir=str(parent)))
    try:
        manifest = {'units':'mm', 'formats':list(formats), 'title':payload['title'], 'sheets':[]}
        if 'dxf_r12' in formats:
            manifest.update(dxf_version='R12', mozaik_import_verified=False,
                            r12_layer_names=r12_layer_names(payload['palette']))
        for sheet in sheets:
            drawing = namespace['Dxf'](payload['palette'])
            drawing.entities = sheet['entities'];drawing.layers = sheet['layers']
            basename = 'Sheet_%02d_%sMM_UP' % (sheet['index'], namespace['token'](sheet['thickness_mm']))
            files = write_drawing(drawing, staging, basename, formats, sheet['width_mm'], sheet['height_mm'])
            manifest['sheets'].append(dict(index=sheet['index'], width_mm=sheet['width_mm'], height_mm=sheet['height_mm'],
                thickness_mm=sheet['thickness_mm'], files=files))
        (staging/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        notes = 'Drawings use millimetres. SVG page dimensions are 1:1.\nREFERENCE and LABELS layers are not cuts. Set tools, depths and toolpaths in CAM.\nOnly the UP machining setup is drawn. Check underside operations in the model or export the complete package.\n'
        if 'dxf_r12' in formats:
            notes += 'Mozaik preset: ACAD R12, closed 2D polylines only, exact arc bulges; guides and text omitted. Coordinates are millimetres: choose mm on import. R12 uses indexed colours.\nThese Sheet_* files are nested sheet drawings. For Mozaik part import, use individual-part *_R12.dxf files from a complete package, not the nested sheets. Create a new layout if individual parts are unavailable.\nTools are not assigned automatically. Actual Mozaik import remains unverified.\nR12 layer names (see manifest.json for the full mapping):\n'
            notes += ''.join('%s = %s\n' % (short,original) for original,short in manifest['r12_layer_names'].items())
        (staging/'SHEET_NOTES.txt').write_text(notes, encoding='utf-8')
        if 'dxf_r12' in formats:write_r12_layer_guide(staging, payload['palette'])
        destination = parent / (namespace['safe_name'](payload['title'])+'_sheets_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        staging.rename(destination)
        return destination, manifest
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def export_dialog(obj):
    import FreeCADGui as Gui
    from PySide import QtWidgets, QtCore, QtGui
    parent = Gui.getMainWindow()
    try:
        root = obj if 'ExportPayload' in obj.PropertiesList else obj.LayoutRoot
        data = json.loads(root.ExportPayload)
        dialog = QtWidgets.QDialog(parent);dialog.setWindowTitle('Export sheet layout')
        layout = QtWidgets.QFormLayout(dialog)
        scope = 'All sheets' if 'ExportPayload' in obj.PropertiesList else 'Sheet %d' % obj.SheetNumber
        layout.addRow('Export', QtWidgets.QLabel(scope))
        format_box = QtWidgets.QComboBox()
        for label, formats in FORMAT_CHOICES:format_box.addItem(label, formats)
        format_box.setObjectName('LayFlatExportFormat');layout.addRow('Format', format_box)
        folder = QtWidgets.QLineEdit(str(Path.home()/'Documents'));folder.setObjectName('LayFlatExportFolder')
        row = QtWidgets.QHBoxLayout();row.addWidget(folder);browse = QtWidgets.QPushButton('Browse…');row.addWidget(browse)
        layout.addRow('Folder', row)
        def choose_folder():
            try:
                chosen = QtWidgets.QFileDialog.getExistingDirectory(dialog, 'Choose export folder', folder.text())
                if chosen:folder.setText(chosen)
            except Exception as exc:QtWidgets.QMessageBox.warning(dialog, 'Folder unavailable', str(exc))
        browse.clicked.connect(choose_folder)
        package = QtWidgets.QCheckBox('Include individual parts, STEP files and part lists')
        package.setObjectName('LayFlatCompletePackage')
        package.setEnabled(scope=='All sheets' and bool(data.get('parts')))
        package.setChecked(package.isEnabled())
        if not data.get('parts'):
            package.setToolTip('This older layout contains sheet drawings only. Create a new layout from the original model to include individual parts and part lists.')
        elif scope != 'All sheets':
            package.setToolTip('Choose Export all sheets to include individual parts and part lists.')
        layout.addRow(package)
        note = QtWidgets.QLabel('A new folder is created for each export. Existing exports are kept. SVG uses millimetres at 1:1 scale.')
        note.setWordWrap(True);layout.addRow(note)
        def explain_format():
            if 'dxf_r12' in format_box.currentData():
                text = 'Closed polylines in millimetres; guides and labels omitted. Select mm on import. Mozaik import is unverified; assign tools in Mozaik.'
                text += (' Use individual-part files from the complete package for Mozaik part import.' if package.isEnabled()
                         else ' This exports nested sheet drawings. Create a new layout and use Export all sheets for individual-part import files.')
                note.setText(text)
            else:
                note.setText('A new folder is created for each export. Existing exports are kept. SVG uses millimetres at 1:1 scale.')
            note.setMinimumHeight(max(0, note.heightForWidth(note.width())))
            dialog.layout().activate()
            dialog.adjustSize()
        format_box.currentIndexChanged.connect(explain_format)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.button(QtWidgets.QDialogButtonBox.Ok).setText('Export')
        buttons.rejected.connect(dialog.reject);layout.addRow(buttons)
        def perform_export():
            busy = False
            try:
                formats = format_box.currentData()
                QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor);busy=True
                destination, manifest = export_layout(obj, folder.text(), formats, package.isChecked())
                QtWidgets.QApplication.restoreOverrideCursor();busy=False
                dialog.accept()
                box = QtWidgets.QMessageBox(parent);box.setWindowTitle('Sheet export saved')
                box.setText('%d sheet(s) exported.\n\n%s' % (len(manifest['sheets']), destination))
                box.setStandardButtons(QtWidgets.QMessageBox.Ok)
                open_button = box.addButton('Open export folder', QtWidgets.QMessageBox.ActionRole)
                box.exec()
                if box.clickedButton() == open_button and not QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(destination))):
                    raise RuntimeError('The files were saved, but the export folder could not be opened.')
            except Exception as exc:
                if busy:QtWidgets.QApplication.restoreOverrideCursor()
                App.Console.PrintError(traceback.format_exc()+'\n')
                QtWidgets.QMessageBox.warning(dialog, 'Export needs attention', str(exc))
        buttons.accepted.connect(perform_export)
        dialog.exec()
    except Exception as exc:
        App.Console.PrintError(traceback.format_exc()+'\n')
        QtWidgets.QMessageBox.warning(parent, 'Export needs attention', str(exc))


class SheetLayoutViewProvider:
    def __init__(self, view):
        view.Proxy = self

    def attach(self, view):
        self.Object = view.Object

    def claimChildren(self):
        return self.Object.Group

    def setupContextMenu(self, view, menu):
        text = 'Export all sheets…' if 'ExportPayload' in view.Object.PropertiesList else 'Export this sheet…'
        action = menu.addAction(text)
        action.triggered.connect(lambda *_: export_dialog(view.Object))
        return False

    def getIcon(self):
        return ':/icons/Std_Group.svg'

    def dumps(self):
        return None

    def loads(self, state):
        return None
