"""FreeCAD integration tests for operation-first sheet previews."""
from pathlib import Path
import tempfile
import unittest
import FreeCAD as App
import Part

path = Path(__file__).resolve().parents[1] / 'FreeCAD_Lay_Flat_for_CNC.FCMacro'
macro = {'__name__': 'preview_test', '__file__': str(path)}
exec(compile(path.read_text(), str(path), 'exec'), macro)


class SheetOperationGroupTests(unittest.TestCase):
    def setUp(self):
        self.previous = App.ActiveDocument
        self.temp = tempfile.TemporaryDirectory(prefix='layflat-preview-test-')
        self.opened = []
        shape = Part.makeBox(80, 50, 18)
        shape = shape.cut(Part.makeCylinder(5, 20, App.Vector(15, 15, -1)))
        shape = shape.cut(Part.makeCylinder(5, 4, App.Vector(35, 15, 15)))
        shape = shape.cut(Part.makeBox(10, 10, 7, App.Vector(55, 10, 12)))
        self.part = macro['apply_part_options'](macro['analyse_solid'](shape, 'Panel'))
        profile = dict(width_mm=240, height_mm=120, margin_mm=5, gap_mm=5, grain_axis='NONE')
        self.sheets = []
        for number, indices in [(1, [1, 2]), (2, [3])]:
            self.sheets.append(dict(index=number, width_mm=240, height_mm=120, thickness_mm=18,
                stock_settings=dict(profile), has_back=False,
                placements=[dict(part_index=i, part=self.part, x_mm=10+j*100, y_mm=10)
                            for j, i in enumerate(indices)]))

    def tearDown(self):
        for name in self.opened:
            App.closeDocument(name)
        if self.previous:
            App.setActiveDocument(self.previous.Name)
        self.temp.cleanup()

    def open_preview(self):
        path = Path(self.temp.name) / 'Sheet_layout.FCStd'
        macro['save_sheet_preview'](self.sheets, {}, path)
        doc = App.openDocument(str(path))
        self.opened.append(doc.Name)
        return doc

    def test_reopened_preview_has_one_item_per_layer_per_sheet(self):
        doc = self.open_preview()
        sheets = doc.getObject('SheetLayouts').Group
        all_labels = []
        for sheet, saved in zip(self.sheets, sheets):
            objects = [o for o in saved.Group if 'DxfLayer' in o.PropertiesList]
            expected = {g['layer']: g for g in macro['grouped_sheet_operations'](sheet, 'FRONT')}
            self.assertEqual(len(objects), len(expected))
            self.assertEqual({o.DxfLayer for o in objects}, set(expected))
            for obj in objects:
                group = expected[obj.DxfLayer]
                self.assertEqual(obj.FeatureCount, group['feature_count'])
                self.assertEqual(obj.PartCount, len(sheet['placements']))
                self.assertEqual(obj.WireCount, len(group['wires']))
                self.assertEqual(obj.Label, '%s (Sheet %d)' % (macro['operation_description'](group['operation']), sheet['index']))
                original = Part.makeCompound(group['wires'])
                original.translate(App.Vector(0, (sheet['index']-1)*270, 0))
                self.assertAlmostEqual(obj.Shape.Length, original.Length, places=6)
                self.assertAlmostEqual(obj.Shape.common(original).Length, original.Length, places=6)
                all_labels.append(obj.Label)
            self.assertTrue(any(o.Label.startswith('Guides — not cuts') for o in saved.Group))
        self.assertEqual(len(all_labels), len(set(all_labels)))
        self.assertFalse(any(o.Name.startswith('Panel') and o.TypeId=='App::DocumentObjectGroup' for o in doc.Objects))
        self.assertFalse(doc.getObject('ReferenceSolids').ViewObject.Visibility)

    def test_same_diameter_different_depths_stay_separate(self):
        groups = macro['grouped_sheet_operations'](self.sheets[0], 'FRONT')
        holes = [g for g in groups if g['operation']['kind']=='HOLE']
        self.assertEqual(len(holes), 2)
        descriptions = [macro['operation_description'](g['operation']) for g in holes]
        self.assertIn('Holes — diameter 10 mm — through', descriptions)
        self.assertIn('Holes — diameter 10 mm — depth 3 mm', descriptions)
        self.assertTrue(all(g['feature_count']==2 for g in holes))

    def test_preview_does_not_change_dxf_or_custom_layer_names(self):
        layer = 'HOLE_D10_THROUGH'
        styled = macro['apply_layer_settings']([self.part], {layer: {'name':'Ten mm through holes', 'hex':'#123456'}})[0]
        self.sheets[0]['placements'][0]['part'] = styled
        # Apply the same layer settings to every part, as the export dialog does.
        for sheet in self.sheets:
            for placement in sheet['placements']:
                placement['part'] = styled
        before = Path(self.temp.name) / 'before.dxf'
        after = Path(self.temp.name) / 'after.dxf'
        macro['sheet_drawing'](self.sheets[0], 'FRONT', {}).save(before)
        doc = self.open_preview()
        macro['sheet_drawing'](self.sheets[0], 'FRONT', {}).save(after)
        self.assertEqual(before.read_bytes(), after.read_bytes())
        objects = [o for o in doc.Objects if 'DxfLayer' in o.PropertiesList and o.DxfLayer=='Ten mm through holes']
        self.assertEqual(len(objects), 2)
        self.assertTrue(all(o.Label.startswith('Ten mm through holes — Holes — diameter 10 mm — through') for o in objects))

    def test_guide_description_is_explicit(self):
        op = dict(kind='EDGE_ROUND', layer='REFERENCE_EDGE_ROUND_R1MM', radius_mm=1, reference_only=True)
        self.assertEqual(macro['operation_description'](op), 'Roundover — radius 1 mm — guide only')


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SheetOperationGroupTests))
    if not result.wasSuccessful():
        raise RuntimeError('Sheet operation grouping tests failed')
