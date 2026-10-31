# First public-data training result

A real supporting crop classifier was trained; Gemma was NOT fine-tuned.

- Source: 2,009 real annotated images, CC BY 4.0, https://zenodo.org/records/17834373
- Usable crops: 3,853. Other labelled defects are cracks and manholes.
- Source/date/perceptual grouping: 339 groups; approximate splits by groups, not equal crop counts.
- Train / validation / test crops: 3,466 / 258 / 129.
- Model: HOG features and balanced linear SVM trained by SGD.
- Selected alpha 0.01 using validation only. The test set was not used to select the model.

| Metric on held-out crops | Learned model | Majority-class baseline |
|---|---:|---:|
| Accuracy | 79.8% | 82.2% |
| Balanced accuracy | 75.8% | 50.0% |
| Pothole recall | 69.6% | 0% |
| Pothole precision | 45.7% | Undefined (no pothole predictions) |

The model recognizes some potholes but its raw accuracy is below the majority baseline. It mislabels too many other defects as potholes. It is an experimental baseline, not a deployment-ready model. Only 23 positive test crops were available; capture groups and nearby sites may still be correlated. No confidence interval implying independent crop samples is claimed.

No repair-review accuracy can be calculated from this dataset because it does not contain verified repair pairs. These are crop-classification results, not detector mAP or before/after repair verification. The trained component remains separate from closure/review decisions.

Artifacts: crop-classifier.npz (numeric coefficients), report.json, split-manifest.json. Training is reproducible through training/README.md. Next work: representative negatives, a new external validation set, then any model changes selected using development data. Do not optimize on this reported test split.
