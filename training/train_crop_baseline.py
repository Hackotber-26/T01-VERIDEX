"""Train a supporting pothole-vs-other-annotated-defect classifier, NOT repair verification."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import zipfile
import cv2
import numpy as np
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import SGDClassifier
from sklearn.dummy import DummyClassifier


def feature(image):
    image=cv2.resize(image,(64,64),interpolation=cv2.INTER_AREA)
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    return cv2.HOGDescriptor((64,64),(16,16),(8,8),(8,8),9).compute(gray).ravel()


def phash(image):
    small=cv2.resize(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),(32,32)).astype(np.float32)
    values=cv2.dct(small)[:8,:8].ravel()[1:]
    return sum(int(v>np.median(values))<<i for i,v in enumerate(values))


def unpack(archive, destination):
    destination=Path(destination).resolve();destination.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        if sum(f.file_size for f in z.infolist())>3_000_000_000:raise ValueError('Archive too large')
        for f in z.infolist():
            target=(destination/f.filename).resolve()
            if not target.is_relative_to(destination):raise ValueError('Unsafe archive path')
        z.extractall(destination)
    return destination


def train(root, output, class_id, annotation_format='polygon'):
    root=Path(root);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    images=sorted(p for p in root.rglob('*') if p.suffix.lower() in {'.jpg','.jpeg','.png'})
    labels={p.stem:p for p in root.rglob('*.txt') if p.name not in {'classes.txt'}}
    parents=list(range(len(images)))
    def find(i):
        while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
        return i
    def union(i,j):parents[find(i)]=find(j)
    hashes=[];samples=[];skipped=Counter();seen={};sequence={}
    for idx,path in enumerate(images):
        if path.stem not in labels:continue
        im=cv2.imread(str(path))
        if im is None:skipped['decode']+=1;continue
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in seen:union(idx,seen[digest])
        seen[digest]=idx
        h=phash(im)
        for old,oldhash in hashes:
            if (h^oldhash).bit_count()<=6:union(idx,old)
        hashes.append((idx,h))
        # Group VLC frame runs by capture date when encoded in filename.
        match=re.search(r'(vlcsnap-\d{4}-\d\d-\d\d|^\d{8}(?=_))',path.stem)
        if match:
            key=match.group(1)
            if key in sequence:union(idx,sequence[key])
            sequence[key]=idx
        height,width=im.shape[:2]
        for line_num,line in enumerate(labels[path.stem].read_text().splitlines()):
            if not line.strip():continue
            try:
                vals=[float(x) for x in line.split()];label=int(vals[0]);coords=vals[1:]
                if not all(np.isfinite(coords)) or any(v<0 or v>1 for v in coords):raise ValueError()
                if annotation_format=='polygon' and len(coords)==8:
                    xs=coords[::2];ys=coords[1::2];x1,x2=min(xs),max(xs);y1,y2=min(ys),max(ys)
                elif annotation_format=='box' and len(coords)==4:
                    cx,cy,bw,bh=coords;x1,x2=cx-bw/2,cx+bw/2;y1,y2=cy-bh/2,cy+bh/2
                else:raise ValueError()
                x1,x2=max(0,int(x1*width)),min(width,int(x2*width));y1,y2=max(0,int(y1*height)),min(height,int(y2*height))
                if x2-x1<16 or y2-y1<16:skipped['tiny_crop']+=1;continue
                crop=im[y1:y2,x1:x2]
                samples.append({'x':feature(crop),'y':int(label==class_id),'image_index':idx,
                                'source':str(path.relative_to(root)),'line':line_num,'source_class':label})
            except (ValueError,IndexError):skipped['invalid_annotation']+=1
    if not samples:raise ValueError('No usable crops: check label layout/format')
    X=np.stack([s['x'] for s in samples]);y=np.array([s['y'] for s in samples]);groups=np.array([find(s['image_index']) for s in samples])
    if len(set(groups))<5:raise ValueError('Too few independent groups after deduplication')
    splitter=GroupShuffleSplit(n_splits=1,test_size=.2,random_state=42)
    development,test=next(splitter.split(X,y,groups))
    trainrel,valrel=next(GroupShuffleSplit(n_splits=1,test_size=.25,random_state=43).split(X[development],y[development],groups[development]))
    tr,va=development[trainrel],development[valrel]
    for indices in [tr,va,test]:
        if len(set(y[indices]))<2:raise ValueError('A split has only one class; collect more independent data')
    choices=[]
    print('Prepared',len(samples),'crops in',len(set(groups)),'groups',flush=True)
    for C in [.0001,.001,.01]:
        model=make_pipeline(StandardScaler(),SGDClassifier(loss='hinge',alpha=C,class_weight='balanced',max_iter=2000,tol=.001,random_state=42))
        model.fit(X[tr],y[tr]);choices.append((balanced_accuracy_score(y[va],model.predict(X[va])),C,model))
    best=max(choices,key=lambda c:c[0]);model=best[2]
    # Keep exact validated train-only model, do not refit on validation/test.
    predictions=model.predict(X[test]);dummy=DummyClassifier(strategy='most_frequent').fit(X[tr],y[tr])
    scaler=model.steps[0][1];svm=model.steps[1][1]
    np.savez(output/'crop-classifier.npz',mean=scaler.mean_,scale=scaler.scale_,coef=svm.coef_,intercept=svm.intercept_)
    manifest=[]
    for split,indices in [('train',tr),('validation',va),('test',test)]:
        for i in indices:
            s=samples[i];manifest.append({k:v for k,v in s.items() if k!='x'}|{'split':split,'group':int(groups[i])})
    (output/'split-manifest.json').write_text(json.dumps(manifest,indent=2))
    report={'task':'pothole crop versus other labelled defects; NOT repair verification',
            'model':'HOG + standardized linear SVM trained by SGD','pothole_source_class_id':class_id,
            'total_images_found':len(images),'usable_crops':len(samples),'group_count':len(set(groups)),
            'split_crops':{'train':len(tr),'validation':len(va),'test':len(test)},
            'source_class_crop_counts':dict(Counter(s['source_class'] for s in samples)),
            'train_class_counts':dict(Counter(map(int,y[tr]))),'test_class_counts':dict(Counter(map(int,y[test]))),
            'skipped':dict(skipped),'selected_alpha':best[1],'validation_balanced_accuracy':best[0],
            'test_accuracy':accuracy_score(y[test],predictions),'test_balanced_accuracy':balanced_accuracy_score(y[test],predictions),
            'dummy_test_accuracy':accuracy_score(y[test],dummy.predict(X[test])),
            'dummy_test_balanced_accuracy':balanced_accuracy_score(y[test],dummy.predict(X[test])),
            'test_confusion_matrix':confusion_matrix(y[test],predictions,labels=[0,1]).tolist(),
            'classification_report':classification_report(y[test],predictions,labels=[0,1],target_names=['other_annotated_defect','pothole'],output_dict=True,zero_division=0),
            'limitations':['No repair pairs; no repair-verification accuracy.',
              'Source-image, exact duplicate, pHash and VLC-date grouping reduce leakage; unrecorded shared sites may remain.',
              'Other class contains labelled cracks/manholes, not representative arbitrary background.',
              'One source dataset; no Bengaluru external validation. Not integrated into closure decisions.']}
    (output/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive');p.add_argument('--root',required=True);p.add_argument('--output',required=True);p.add_argument('--pothole-class',type=int,required=True);p.add_argument('--format',choices=['polygon','box'],default='polygon');a=p.parse_args()
    root=unpack(a.archive,a.root) if a.archive else Path(a.root)
    train(root,a.output,a.pothole_class,a.format)
