# Public source and training scope

Dataset: Road Damage Dataset: Potholes, Cracks and Manholes.
Authors: Enrico Giordani, Lorenzo Arcioni, Manuel Gil-Martín and Marco Raoul Marini.
Source: https://zenodo.org/records/17834373
DOI: https://doi.org/10.5281/zenodo.17834373
License: Creative Commons Attribution 4.0 International, https://creativecommons.org/licenses/by/4.0/
Record metadata is saved in record.json. Original archive MD5: ef8b402e9f7ee7d2e64919f21ad6ab6a.

Class mapping 0=pothole, 1=crack, 2=manhole confirmed from authors' dataset_eda.ipynb:
https://github.com/lorenzo-arcioni/Road-Damage-Detection-Dataset-Analysis/blob/main/analysis/dataset_eda.ipynb
We implemented independent training code; we did not copy their GPL training implementation.

Modifications: extract provided annotated rectangles, discard invalid/tiny annotations, resize crops, compute HOG features, fit a linear SVM with a validation set. Raw dataset files remain unchanged. Dataset copyright and attribution remain with the authors.

This source contains detection annotations, NOT longitudinal repair pairs or evidence-sufficiency labels. It cannot train Gemma to verify repairs or provide repair-review accuracy. No synthetic after-image is represented as a real repair in this training experiment.
