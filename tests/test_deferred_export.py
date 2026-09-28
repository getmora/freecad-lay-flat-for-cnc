"""Run inside FreeCAD: deferred menus, persistence, SVG and complete packages."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import FreeCAD as App
import Part

repo = Path(__file__).resolve().parents[1]
if str(repo) not in sys.path:sys.path.insert(0, str(repo))
import lay_flat_sheet as runtime
ns = {'__name__':'deferred_test', '__file__':str(repo/'FreeCAD_Lay_Flat_for_CNC.FCMacro')}
exec(compile((repo/'FreeCAD_Lay_Flat_for_CNC.FCMacro').read_text(), ns['__file__'], 'exec'), ns)


class DeferredExportTests(unittest.TestCase):
    def setUp(self):
        self.previous = App.ActiveDocument
        self.temp = tempfile.TemporaryDirectory(prefix='layflat-deferred-')
        self.folder = Path(self.temp.name)
        shape = Part.makeBox(100, 60, 18)
        shape = shape.makeFillet(5, [e for e in shape.Edges if e.BoundBox.ZLength > 17.9])
        shape = shape.cut(Part.makeCylinder(3, 20, App.Vector(20, 20, -1)))
        part = ns['apply_part_options'](ns['analyse_solid'](shape, 'Arc panel'))
        self.parts = [part, dict(part, label='Second panel')]
        self.settings = dict(width_mm=130, height_mm=90, margin_mm=5, gap_mm=5, grain_axis='X')
        self.sheets = ns['pack_sheets'](self.parts, self.settings)
        self.doc = ns['save_sheet_preview'](self.sheets, self.settings, title='Deferred test')
        self.root = self.doc.getObject('SheetLayouts')

    def tearDown(self):
        if self.doc.Name in App.listDocuments():App.closeDocument(self.doc.Name)
        if self.previous:App.setActiveDocument(self.previous.Name)
        self.temp.cleanup()

    def test_creation_does_not_export_and_menu_exists(self):
        from PySide import QtWidgets
        self.assertEqual(self.doc.FileName, '')
        self.assertEqual(list(self.folder.iterdir()), [])
        menu = QtWidgets.QMenu()
        self.root.ViewObject.Proxy.setupContextMenu(self.root.ViewObject, menu)
        self.assertIn('Export all sheets…', [a.text() for a in menu.actions()])

    def test_single_sheet_svg_is_mm_and_preserves_curves(self):
        sheet = self.root.Group[0]
        folder, manifest = runtime.export_layout(sheet, self.folder, ('svg',))
        self.assertEqual(len(manifest['sheets']), 1)
        self.assertFalse(list(folder.glob('*.dxf')))
        svg = ET.parse(next(folder.glob('*.svg'))).getroot()
        self.assertEqual(svg.get('width'), '130mm')
        self.assertEqual(svg.get('height'), '90mm')
        self.assertEqual(svg.get('viewBox'), '0 0 130 90')
        layers = {g.get('data-layer') for g in svg.findall('{%s}g' % runtime.SVG_NS)}
        self.assertIn('OUTLINE_THROUGH', layers)
        self.assertIn('HOLE_D6_THROUGH', layers)
        self.assertTrue(any('A ' in p.get('d') for p in svg.iter('{%s}path' % runtime.SVG_NS)))
        self.assertEqual(len(list(svg.iter('{%s}circle' % runtime.SVG_NS))), 1)

    def test_both_formats_and_repeated_exports(self):
        first, _ = runtime.export_layout(self.root, self.folder, ('dxf','svg'))
        before = {p.name:p.read_bytes() for p in first.iterdir()}
        second, _ = runtime.export_layout(self.root, self.folder, ('dxf','svg'))
        self.assertNotEqual(first, second)
        self.assertEqual(len(list(first.glob('*.dxf'))), 2)
        self.assertEqual(len(list(first.glob('*.svg'))), 2)
        self.assertEqual(before, {p.name:p.read_bytes() for p in first.iterdir()})

    def test_complete_svg_package_retains_parts_and_preview(self):
        folder, manifest = runtime.export_layout(self.root, self.folder, ('svg',), True)
        self.assertEqual(len(manifest['parts']), 2)
        self.assertEqual(len(list(folder.glob('*.step'))), 2)
        self.assertEqual(len(list(folder.glob('*.svg'))), 4)
        self.assertFalse(list(folder.glob('*.dxf')))
        self.assertTrue((folder/'Flat_parts.FCStd').is_file())
        self.assertTrue(manifest['preview']['created'], manifest['preview'])

    def test_reopen_restores_menu_without_running_macro(self):
        from PySide import QtWidgets
        path = self.folder/'Saved.FCStd';self.doc.saveAs(str(path))
        App.closeDocument(self.doc.Name)
        self.doc = App.openDocument(str(path));self.root = self.doc.getObject('SheetLayouts')
        self.assertIsNotNone(self.root.ViewObject.Proxy)
        menu = QtWidgets.QMenu();self.root.ViewObject.Proxy.setupContextMenu(self.root.ViewObject, menu)
        self.assertIn('Export all sheets…', [a.text() for a in menu.actions()])
        folder, _ = runtime.export_layout(self.root, self.folder, ('svg',))
        self.assertEqual(len(list(folder.glob('*.svg'))), 2)

    def test_changed_geometry_is_rejected_without_files(self):
        op = next(o for o in self.doc.Objects if 'DxfLayer' in o.PropertiesList)
        copy = op.Shape.copy();copy.translate(App.Vector(1, 0, 0));op.Shape = copy
        with self.assertRaisesRegex(ValueError, 'geometry was edited'):
            runtime.export_layout(self.root, self.folder, ('svg',))
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_svg_arc_direction_and_negative_envelope(self):
        wire = Part.Wire([Part.makeCircle(10, App.Vector(0, 0, 0), App.Vector(0,0,1), 0, 180),
                          Part.makeLine(App.Vector(-10,0,0), App.Vector(10,0,0))])
        drawing = ns['Dxf']();drawing.add_wire(wire, 'OUTLINE_THROUGH')
        path = self.folder/'arc.svg'
        runtime.save_svg(drawing, path, 20, 10, bounds=(-10,0,10,10))
        svg = ET.parse(path).getroot()
        self.assertEqual(svg.get('width'), '20mm')
        d = next(svg.iter('{%s}path' % runtime.SVG_NS)).get('d')
        self.assertIn('A 10 10 0 0 0 0 10', d)
        self.assertIn('M 20 10', d)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DeferredExportTests))
    if not result.wasSuccessful():raise RuntimeError('Deferred export tests failed')
