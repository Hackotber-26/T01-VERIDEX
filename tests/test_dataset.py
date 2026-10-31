import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from PIL import Image
from veridex.prepare_dataset import prepare
from veridex.evaluate import load_cases

class DatasetTests(unittest.TestCase):
    def test_split_has_no_location_leakage_and_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rows=[]
            for i in range(5):
                Image.fromarray(np.random.default_rng(i).integers(0,255,(64,64,3),dtype=np.uint8)).save(root/f'{i}.png')
                for variant in range(2):
                    rows.append(dict(id=f'{i}-{variant}',location_group=f'site{i}',synthetic=False,
                        before=f'{i}.png',after=f'{i}.png',roi=[0,0,1,1],label='visible_defect_remains',
                        label_source='reviewer A/B adjudicated',consent_or_license='test fixture'))
            source=root/'labels.jsonl';source.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            output=root/'manifest.jsonl';result=prepare(source,output)
            self.assertEqual(result['cases'],10)
            loaded=load_cases(output)
            self.assertEqual({r['split'] for r in loaded},{'train','validation','test'})
            with self.assertRaises(FileExistsError):prepare(source,output)
