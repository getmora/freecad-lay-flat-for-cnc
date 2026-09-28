"""FreeCAD tests for the Mozaik-targeted closed-polyline R12 preset."""
from pathlib import Path
import math
import tempfile
import unittest
import sys
import FreeCAD as App
import Part

repo = Path(__file__).resolve().parents[1]
if str(repo) not in sys.path:sys.path.insert(0,str(repo))
import lay_flat_sheet as runtime
path = repo/'FreeCAD_Lay_Flat_for_CNC.FCMacro'
ns = {'__name__':'r12_test','__file__':str(path)}
exec(compile(path.read_text(),str(path),'exec'),ns)


def records(path):
    lines=path.read_text().splitlines()
    pairs=list(zip(map(int,lines[::2]),lines[1::2]))
    result=[];entity=[]
    for code,value in pairs:
        if code==0 and entity:result.append(entity);entity=[]
        entity.append((code,value))
    if entity:result.append(entity)
    return pairs,result


class R12ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='layflat-r12-')
        self.folder=Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def drawing(self):
        drawing=ns['Dxf']()
        drawing.add_wire(ns['rectangle_wire'](100,60),'OUTLINE_THROUGH')
        drawing.add_wire(Part.Wire([Part.makeCircle(5,App.Vector(20,20,0))]),'HOLE_D10_THROUGH')
        drawing.add_wire(ns['rectangle_wire'](200,100),'REFERENCE_SHEET')
        drawing.add_line((0,0),(10,10));drawing.add_text('Part 1',0,0)
        return drawing

    def test_only_r12_closed_polylines_are_written(self):
        path=self.folder/'part.dxf';runtime.save_r12(self.drawing(),path)
        pairs,entities=records(path)
        self.assertIn((1,'AC1009'),pairs)
        self.assertFalse(any(code in (100,330,420) for code,_ in pairs))
        self.assertFalse(any(value in ('CIRCLE','LWPOLYLINE','LINE','TEXT') for code,value in pairs if code==0))
        polylines=[dict(e) for e in entities if e[0]==(0,'POLYLINE')]
        self.assertEqual(len(polylines),2)
        self.assertTrue(all(p[70]=='1' and p[66]=='1' for p in polylines))
        self.assertFalse(any(value.startswith('REFERENCE_') for code,value in pairs if code==8))

    def test_circle_is_four_exact_quarter_arcs(self):
        path=self.folder/'circle.dxf';runtime.save_r12(self.drawing(),path)
        _,entities=records(path)
        vertices=[dict(e) for e in entities if e[0]==(0,'VERTEX') and dict(e)[8]=='HOLE_D10_THROUGH']
        self.assertEqual(len(vertices),4)
        for index,v in enumerate(vertices):
            x,y=float(v[10]),float(v[20]);b=float(v[42]);n=vertices[(index+1)%4]
            self.assertAlmostEqual(math.hypot(x-20,y-20),5,places=9)
            radius=math.hypot(float(n[10])-x,float(n[20])-y)*(1+b*b)/(4*abs(b))
            self.assertAlmostEqual(radius,5,places=9)
            self.assertAlmostEqual(4*math.atan(b),math.pi/2,places=9)

    def test_open_cutting_entity_is_rejected(self):
        drawing=ns['Dxf']();drawing.add_line((0,0),(10,10),'CUTTING')
        path=self.folder/'bad.dxf'
        with self.assertRaisesRegex(ValueError,'closed outline'):
            runtime.save_r12(drawing,path)
        self.assertFalse(path.exists())

    def test_custom_layer_aliases_are_unique_and_mapped(self):
        palette=ns['make_layer_palette'](['A B','A_B','HOLE_D6P6_DEPTH_16MM_TIP_17P9828MM','X'*80])
        names=runtime.r12_layer_names(palette)
        self.assertEqual(len(set(names.values())),4)
        self.assertTrue(all(len(name)<=31 for name in names.values()))
        self.assertIn('TIP17P9828',names['HOLE_D6P6_DEPTH_16MM_TIP_17P9828MM'])
        runtime.write_r12_layer_guide(self.folder,palette)
        self.assertIn('X'*80,(self.folder/'R12_LAYERS.csv').read_text())

    def test_renamed_reference_layer_is_omitted(self):
        palette=ns['make_layer_palette'](['OUTLINE_THROUGH'])
        palette['FINISH_GUIDE']=dict(hex='#112233',aci=7,source_layer='REFERENCE_EDGE_ROUND_R1MM')
        drawing=ns['Dxf'](palette)
        drawing.add_wire(ns['rectangle_wire'](100,60),'OUTLINE_THROUGH')
        drawing.add_wire(ns['rectangle_wire'](10,10),'FINISH_GUIDE')
        path=self.folder/'part.dxf';runtime.save_r12(drawing,path)
        _,entities=records(path)
        self.assertEqual(sum(e[0]==(0,'POLYLINE') for e in entities),1)

    def test_complete_package_contains_individual_r12_parts(self):
        previous=App.ActiveDocument
        part=ns['apply_part_options'](ns['analyse_solid'](Part.makeBox(100,60,18).cut(
            Part.makeCylinder(5,20,App.Vector(20,20,-1))),'Panel'))
        settings=dict(width_mm=2440,height_mm=1220,margin_mm=10,gap_mm=10,grain_axis='X')
        sheets=ns['pack_sheets']([part],settings)
        doc=ns['save_sheet_preview'](sheets,settings)
        try:
            folder,manifest=runtime.export_layout(doc.getObject('SheetLayouts'),self.folder,('dxf_r12',),True)
            self.assertEqual(manifest['dxf_version'],'R12')
            self.assertFalse(manifest['mozaik_import_verified'])
            self.assertTrue((folder/'R12_LAYERS.csv').exists())
            part_files=manifest['parts'][0]['files']
            self.assertTrue(part_files and all(name.endswith('_R12.dxf') for name in part_files))
            for name in part_files:
                pairs,_=records(folder/name);self.assertIn((1,'AC1009'),pairs)
        finally:
            App.closeDocument(doc.Name)
            if previous:App.setActiveDocument(previous.Name)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(R12ExportTests))
    if not result.wasSuccessful():raise RuntimeError('R12 export tests failed')
