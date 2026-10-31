# Supporting pothole crop classifier

This is independent CPU training on public real annotated images. It does NOT fine-tune Gemma and does NOT learn whether a repair is complete. It distinguishes an annotated pothole crop from annotated crack/manhole crops using HOG features and a linear SVM.

## Reproduce

Use Python 3.10+ in a separate environment:

    python -m pip install -r training/requirements.txt
    python training/fetch_public.py
    python training/train_crop_baseline.py --archive dataset/public/road-damage-17834373/verified.zip --root dataset/public/road-damage-17834373/extracted --output training/artifacts/crop-baseline-v1 --pothole-class 0

The source download is approximately 193 MB. Its checksum is verified. Extracted files occupy about 200 MB. Training selects SGD regularization alpha from 0.0001, 0.001 and 0.01 using validation balanced accuracy; the test set is evaluated only after selection. The saved model is not refit on test/validation data.

Output: numeric weights in crop-classifier.npz, source/split manifest, and report.json. The numeric weights can be used without scikit-learn:

    python -m training.predict_crop --image path/to/photo.jpg --roi 0.2 0.3 0.7 0.8

Use only labelled or manually selected defect crops; arbitrary background and full-photo detection were not trained. The signed margin is not a probability.

## Split controls and limitations

All crops from the same image share a group. Exact image matches, low-distance perceptual hashes and recognized capture-date filename prefixes are grouped. This is a conservative proxy, not verified physical-site independence. Unrecorded nearby locations and duplicate views can remain. A genuine independent Bengaluru field set is still necessary.

Compare with the majority-class baseline using accuracy AND balanced accuracy, pothole precision/recall and confusion matrix. Do not compare crop classification accuracy with a published detector's mAP. Do not describe this model's metrics as VERIDEX repair-verification accuracy.

The review pipeline continues to use Gemma and AECP. This experimental model does not automatically override any review finding. Before integrating it, collect representative negatives and show it improves a held-out review task without increasing false repair findings.

Source attribution: dataset/public/road-damage-17834373/ATTRIBUTION.md.
