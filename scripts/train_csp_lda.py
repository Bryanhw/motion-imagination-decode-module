"""Fit CSP+LDA on R04/R08 and evaluate once on the held-out R12 run."""
import json
import platform
from pathlib import Path

import joblib
import mne
import numpy as np
import scipy
import sklearn
from mne.decoding import CSP
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix
from sklearn.pipeline import Pipeline

from preprocess import ROOT, prepare_data

ARTIFACTS = ROOT / "artifacts"
MODEL_PATH = ARTIFACTS / "s001_csp_lda.joblib"
METADATA_PATH = ARTIFACTS / "s001_csp_lda.json"
PREDICTIONS_PATH = ARTIFACTS / "r12_predictions.npy"
LABEL_NAMES = {0: "左手想象 (T1)", 1: "右手想象 (T2)"}


def check_inputs(X_train, y_train, X_test, y_test, metadata):
    """Catch split or array mistakes before fitting the supervised CSP step."""
    train_runs = set(metadata["train_runs"])
    if metadata["test_run"] in train_runs or train_runs != {"S001R04.edf", "S001R08.edf"}:
        raise ValueError("训练/测试记录划分错误或重叠")
    if metadata["test_run"] != "S001R12.edf":
        raise ValueError("测试记录必须是 S001R12.edf")
    if X_train.ndim != 3 or X_test.ndim != 3 or y_train.ndim != 1 or y_test.ndim != 1:
        raise ValueError("X 应为三维、y 应为一维")
    if X_train.shape[0] != len(y_train) or X_test.shape[0] != len(y_test):
        raise ValueError("X 片段数与 y 标签数不对应")
    if X_train.shape[1:] != X_test.shape[1:]:
        raise ValueError("训练/测试的通道数或窗口长度不一致")
    if X_train.shape[1] != len(metadata["channel_names"]):
        raise ValueError("X 的通道数与记录的通道顺序不一致")
    expected_points = round((metadata["epoch_seconds"][1] - metadata["epoch_seconds"][0]) * metadata["sfreq"])
    if X_train.shape[2] != expected_points:
        raise ValueError("片段点数与采样率/窗口时间不一致")
    for name, labels in (("训练", y_train), ("测试", y_test)):
        if set(np.unique(labels)) != {0, 1}:
            raise ValueError(f"{name}集必须同时包含左手 0 和右手 1")
    if not np.isfinite(X_train).all() or not np.isfinite(X_test).all():
        raise ValueError("X 含缺失值或无穷大")


def report(y_test, predictions, baseline):
    """Print a labeled confusion matrix and a majority-class baseline."""
    matrix = confusion_matrix(y_test, predictions, labels=[0, 1])
    print(f"R12 准确率：{accuracy_score(y_test, predictions):.3f}")
    print(f"R12 balanced accuracy：{balanced_accuracy_score(y_test, predictions):.3f}")
    print("混淆矩阵：行=真实类别，列=预测类别")
    print("                    预测左手  预测右手")
    print(f"  真实左手 T1         {matrix[0, 0]:2d}        {matrix[0, 1]:2d}")
    print(f"  真实右手 T2         {matrix[1, 0]:2d}        {matrix[1, 1]:2d}")
    print(f"各类识别正确：左手 {matrix[0, 0]}/{matrix[0].sum()}；右手 {matrix[1, 1]}/{matrix[1].sum()}")
    print(f"多数类基线（恒猜 {LABEL_NAMES[int(baseline[0])]}）：准确率 "
          f"{accuracy_score(y_test, baseline):.3f}，balanced accuracy "
          f"{balanced_accuracy_score(y_test, baseline):.3f}")


def main():
    X_train, y_train, X_test, y_test, data_info = prepare_data()
    check_inputs(X_train, y_train, X_test, y_test, data_info)
    print(f"训练：{len(y_train)} 段；左 {(y_train == 0).sum()}、右 {(y_train == 1).sum()}")
    print(f"测试：{len(y_test)} 段；左 {(y_test == 0).sum()}、右 {(y_test == 1).sum()}")

    # Pipeline.fit calls CSP.fit only with X_train/y_train. R12 is used for prediction.
    model = Pipeline([
        ("csp", CSP(n_components=4, reg=None, log=True, norm_trace=False)),
        ("lda", LinearDiscriminantAnalysis(solver="svd")),
    ])
    model.fit(X_train, y_train)
    predictions = model.predict(X_test)
    majority = int(np.argmax(np.bincount(y_train, minlength=2)))
    baseline = np.full_like(y_test, majority)
    report(y_test, predictions, baseline)

    ARTIFACTS.mkdir(exist_ok=True)
    details = {
        "dataset": "PhysioNet EEG Motor Movement/Imagery Dataset",
        "dataset_version": "1.0.0",
        "dataset_url": "https://physionet.org/content/eegmmidb/1.0.0/",
        "subject": "S001",
        "train_runs": list(data_info["train_runs"]),
        "test_run": data_info["test_run"],
        "labels": {str(key): name for key, name in LABEL_NAMES.items()},
        "channel_names": data_info["channel_names"],
        "sfreq_hz": data_info["sfreq"],
        "filter": {"kind": "causal Butterworth SOS bandpass", "low_high_hz": data_info["filter_hz"],
                   "order": data_info["filter_order"], "initial_state": "zeros per recording"},
        "epoch_seconds_after_cue": data_info["epoch_seconds"],
        "epoch_samples": int(X_train.shape[2]),
        "model": {"pipeline": ["CSP", "LDA"], "csp": {"n_components": 4, "reg": None,
                   "log": True, "norm_trace": False}, "lda": {"solver": "svd"}},
        "dependency_versions": {"python": platform.python_version(), "mne": mne.__version__,
                                "numpy": np.__version__, "scipy": scipy.__version__,
                                "scikit_learn": sklearn.__version__, "joblib": joblib.__version__},
    }
    joblib.dump(model, MODEL_PATH)
    METADATA_PATH.write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
    np.save(PREDICTIONS_PATH, predictions)
    print(f"已保存 Pipeline：{MODEL_PATH}")
    print(f"已保存元数据：{METADATA_PATH}")
    print(f"已保存 R12 预测供加载核验：{PREDICTIONS_PATH}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(f"训练或核验失败：{error}")
