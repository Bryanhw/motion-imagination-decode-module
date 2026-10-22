# EEGMMIDB subject 001 motor imagery recordings

These three unmodified EDF+ files were already present in the project workspace and are copied here to make the demo replay reproducible:

- `S001R04.edf`
- `S001R08.edf`
- `S001R12.edf`

They are recordings from runs 4, 8, and 12 for subject 001 in PhysioNet's EEG Motor Movement/Imagery Dataset. The dataset contains 64-channel EEG recorded at 160 Hz with embedded task annotations. In these runs, T1/T2 mark imagined left/right fist tasks and T0 marks rest. See the dataset page for the full protocol and details:

<https://physionet.org/content/eegmmidb/1.0.0/>

PhysioNet states that unaltered data from its site may be copied and redistributed without restrictions; these files are redistributed unmodified with attribution to PhysioNet and the dataset contributors. Source data are included for reproducibility and integration testing only. Do not treat outputs from the project's demonstration model as a valid EEG classification score: that model is a synthetic engineering demo, not a model trained on these EDF recordings.

The files are small (< 3 MB each), anonymized public research data, and their original EDF+ annotations are retained. Converted/resampled test artifacts and trained models are generated locally under the ignored `artifacts/` folder and are not committed.
