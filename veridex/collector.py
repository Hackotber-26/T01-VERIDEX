"""Consent-gated local dataset storage shared by all registered client apps."""
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import shutil
import uuid
from .policy import decide, parse_observation
from .evaluate import LABELS

class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, app TEXT NOT NULL, payload TEXT NOT NULL)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.root/'cases.sqlite3', timeout=30)
        try:
            with db:
                yield db
        finally:
            db.close()

    def save(self, app, before, after, roi, result, receipt, site_group):
        if not isinstance(receipt, str) or not receipt.strip() or len(receipt)>200:
            raise ValueError('A non-identifying training consent receipt reference is required')
        if not isinstance(site_group, str) or not site_group.strip() or len(site_group)>200:
            raise ValueError('An opaque site_group is required for location-based splits')
        case_id = uuid.uuid4().hex
        folder = self.root/'images'/case_id
        folder.mkdir(parents=True)
        # Re-encode metadata-free images, retaining original case geometry.
        before.save(folder/'before.jpg', format='JPEG', quality=90)
        after.save(folder/'after.jpg', format='JPEG', quality=90)
        payload = dict(id=case_id, app_id=app, before=f'images/{case_id}/before.jpg',
            after=f'images/{case_id}/after.jpg', roi=roi, ai_result=result,
            location_group=hashlib.sha256((app+'|'+site_group).encode()).hexdigest(),
            training_consent=True, consent_receipt=receipt, label=None,
            label_source=None, observation=None, export_approved=False,
            synthetic=False, human_reviewed=False)
        with self.connect() as db:
            db.execute('INSERT INTO cases VALUES (?,?,?)',(case_id, app, json.dumps(payload)))
        return case_id

    def get(self, app, case_id):
        with self.connect() as db:
            row=db.execute('SELECT payload FROM cases WHERE id=? AND app=?',(case_id,app)).fetchone()
        if row is None: raise KeyError('Case not found')
        return json.loads(row[0])

    def label(self, app, case_id, label, reviewer, observation=None, approved=False, synthetic=False):
        if label not in LABELS: raise ValueError('Invalid label')
        if not isinstance(reviewer,str) or not reviewer.strip() or len(reviewer)>100:
            raise ValueError('Provide an opaque reviewer reference, not personal details')
        if type(approved) is not bool or type(synthetic) is not bool: raise ValueError('Invalid flags')
        if observation is not None:
            observation=parse_observation(json.dumps(observation))
            if decide(observation)['outcome']!=label: raise ValueError('Observation conflicts with human label')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT payload FROM cases WHERE id=? AND app=?',(case_id,app)).fetchone()
            if row is None: raise KeyError('Case not found')
            item=json.loads(row[0])
            item.update(label=label, label_source='human reviewer '+reviewer,
                        observation=observation, export_approved=approved,
                        synthetic=synthetic, human_reviewed=True)
            db.execute('UPDATE cases SET payload=? WHERE id=? AND app=?',(json.dumps(item),case_id,app))
        return item

    def withdraw(self, app, case_id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT payload FROM cases WHERE id=? AND app=?',(case_id,app)).fetchone()
            if row is None: raise KeyError('Case not found')
            item=json.loads(row[0]);item.update(training_consent=False,export_approved=False)
            db.execute('UPDATE cases SET payload=? WHERE id=? AND app=?',(json.dumps(item),case_id,app))
        image_folder = self.root/'images'/case_id
        if image_folder.exists():
            shutil.rmtree(image_folder)
        return {'id':case_id,'training_consent':False,'export_approved':False,
                'note':'Excluded from future exports. Previously uploaded Git history needs separate removal.'}

    def eligible(self):
        with self.connect() as db: rows=db.execute('SELECT payload FROM cases').fetchall()
        return [item for row in rows if (item:=json.loads(row[0]))['training_consent']
                and item['human_reviewed'] and item['export_approved']]
