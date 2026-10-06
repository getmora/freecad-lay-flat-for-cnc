"""FreeCAD tests for the standard AC1018 DXF object graph (VCarve/ODA readers)."""
from pathlib import Path
import tempfile
import unittest
import sys
import FreeCAD as App
import Part

repo = Path(__file__).resolve().parents[1]
if str(repo) not in sys.path:sys.path.insert(0,str(repo))
path = repo/'FreeCAD_Lay_Flat_for_CNC.FCMacro'
ns = {'__name__':'dxf_structure_test','__file__':str(path)}
exec(compile(path.read_text(encoding='utf-8'),str(path),'exec'),ns)


def records(path):
    lines=path.read_text().splitlines()
    pairs=list(zip(map(int,lines[::2]),lines[1::2]))
    result=[];entity=[]
    for code,value in pairs:
        if code==0 and entity:result.append(entity);entity=[]
        entity.append((code,value))
    if entity:result.append(entity)
    return pairs,result


class DxfStructureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='layflat-dxf-')
        drawing=ns['Dxf']()
        drawing.add_wire(ns['rectangle_wire'](100,60),'OUTLINE_THROUGH')
        drawing.add_wire(Part.Wire([Part.makeCircle(5,App.Vector(20,20,0))]),'HOLE_D10_THROUGH')
        drawing.add_line((0,0),(50,0))
        drawing.add_text('Part 1',5,5)
        self.path=Path(self.temp.name)/'part.dxf'
        drawing.save(self.path)
        self.pairs,self.records=records(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def sections(self):
        return [r[1][1] for r in self.records if r[0]==(0,'SECTION')]

    def test_has_every_r2000_section(self):
        self.assertEqual(self.sections(),['HEADER','CLASSES','TABLES','BLOCKS','ENTITIES','OBJECTS'])
        tables=[r[1][1] for r in self.records if r[0]==(0,'TABLE')]
        for name in ('VPORT','LTYPE','LAYER','STYLE','APPID','DIMSTYLE','BLOCK_RECORD'):
            self.assertIn(name,tables)

    def test_entities_are_owned_by_model_space(self):
        model=[r for r in self.records if r[0]==(0,'BLOCK_RECORD') and (2,'*Model_Space') in r]
        self.assertEqual(len(model),1)
        model_handle=dict(model[0])[5]
        geometry=[r for r in self.records if r[0][1] in ('LWPOLYLINE','CIRCLE','LINE','TEXT')]
        self.assertEqual(len(geometry),4)
        for record in geometry:self.assertEqual(dict(record).get(330),model_handle)
        self.assertTrue(any(r[0]==(0,'BLOCK') and (2,'*Model_Space') in r for r in self.records))

    def test_handles_unique_and_below_seed(self):
        handles=[int(v,16) for c,v in self.pairs[self.pairs.index((9,'$HANDSEED'))+2:] if c in (5,105)]
        seed=int(self.pairs[self.pairs.index((9,'$HANDSEED'))+1][1],16)
        self.assertEqual(len(handles),len(set(handles)))
        self.assertTrue(all(h<seed for h in handles))

    def test_owner_pointers_resolve(self):
        handles={v for c,v in self.pairs if c in (5,105)}|{'0'}
        for code,value in self.pairs:
            if code in (330,340,350,390):self.assertIn(value,handles)
        self.assertTrue(any(c==390 for c,_ in self.pairs))

    def test_no_blank_value_lines(self):
        self.assertFalse(any(value=='' for _,value in self.pairs))

    def save(self, drawing):
        path=Path(self.temp.name)/'extra.dxf'
        drawing.save(path)
        return records(path)

    def header_point(self, pairs, name):
        index=pairs.index((9,name))
        return float(pairs[index+1][1]), float(pairs[index+2][1])

    def test_text_records_close_subclass_and_empty_labels_are_skipped(self):
        drawing=ns['Dxf']()
        drawing.add_wire(ns['rectangle_wire'](10,10),'OUTLINE_THROUGH')
        drawing.add_text('',1,1)
        drawing.add_text('   ',1,1)
        drawing.add_text('Kept',1,1)
        _,result=self.save(drawing)
        texts=[r for r in result if r[0]==(0,'TEXT')]
        self.assertEqual(len(texts),1)
        self.assertEqual(texts[0][-1],(100,'AcDbText'))

    def test_empty_drawing_is_still_structurally_complete(self):
        pairs,result=self.save(ns['Dxf']())
        self.assertIn((2,'OBJECTS'),pairs)
        self.assertTrue(any(r[0]==(0,'BLOCK_RECORD') for r in result))
        self.assertEqual(self.header_point(pairs,'$EXTMIN'),(0.0,0.0))
        self.assertEqual(self.header_point(pairs,'$EXTMAX'),(1.0,1.0))
        vport=next(r for r in result if r[0]==(0,'VPORT'))
        self.assertGreater(float(dict(vport)[40]),0)

    def test_extents_include_arc_bulges(self):
        # Closed semicircle-ended slot: arcs swell 5 mm past every vertex in y.
        drawing=ns['Dxf']()
        drawing.layers['OUTLINE_THROUGH']=7
        drawing.entities.append([(0,'LWPOLYLINE'),(100,'AcDbEntity'),(8,'OUTLINE_THROUGH'),(100,'AcDbPolyline'),
                                 (90,2),(70,1),(38,0),(10,0.0),(20,0.0),(42,1.0),(10,10.0),(20,0.0),(42,1.0)])
        pairs,_=self.save(drawing)
        for name,expected in (('$EXTMIN',(0.0,-5.0)),('$EXTMAX',(10.0,5.0))):
            for actual,wanted in zip(self.header_point(pairs,name),expected):self.assertAlmostEqual(actual,wanted,places=9)
        # An open polyline's last-vertex bulge does not describe a closing arc.
        drawing.entities[0]=[(70,0) if code==70 else (code,value) for code,value in drawing.entities[0]]
        pairs,_=self.save(drawing)
        self.assertAlmostEqual(self.header_point(pairs,'$EXTMAX')[1],0.0,places=9)
        self.assertEqual(ns['bulge_extremes'](0,0,10,0,0.0),[])
        minor=ns['bulge_extremes'](0,0,10,0,-0.2)
        self.assertEqual(len(minor),1)
        self.assertAlmostEqual(minor[0][0],5.0)
        self.assertGreater(minor[0][1],0)


if __name__=='__main__':unittest.main()
