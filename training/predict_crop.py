"""Use the saved numeric crop baseline without loading pickle or scikit-learn."""
import argparse
import json
import cv2
import numpy as np
from veridex.images import load_image,crop_roi

def predict(image_path,model_path,roi=None):
    image=load_image(image_path)
    if roi:image=crop_roi(image,roi)
    resized=cv2.resize(np.asarray(image),(64,64),interpolation=cv2.INTER_AREA)
    gray=cv2.cvtColor(resized,cv2.COLOR_RGB2GRAY)
    x=cv2.HOGDescriptor((64,64),(16,16),(8,8),(8,8),9).compute(gray).ravel()
    with np.load(model_path,allow_pickle=False) as weights:
        margin=float((((x-weights['mean'])/weights['scale'])@weights['coef'][0])+weights['intercept'][0])
    return {'label':'pothole' if margin>0 else 'other_annotated_defect','signed_margin':margin,
            'calibrated_probability':None,'certifies_repair':False,
            'scope':'Experimental crop classifier; not a full-image detector or repair reviewer.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--image',required=True);p.add_argument('--model',default='training/artifacts/crop-baseline-v1/crop-classifier.npz');p.add_argument('--roi',type=float,nargs=4)
    a=p.parse_args();print(json.dumps(predict(a.image,a.model,a.roi),indent=2))
