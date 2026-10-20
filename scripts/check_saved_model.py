"""Reload our own local Pipeline and compare its R12 predictions."""
import json
import numpy as np
import joblib

from preprocess import prepare_data
from train_csp_lda import MODEL_PATH, METADATA_PATH, PREDICTIONS_PATH, check_inputs


def main():
    # joblib files can execute code when loaded: only use a file you created or trust.
    for path in (MODEL_PATH, METADATA_PATH, PREDICTIONS_PATH):
        if not path.is_file():
            raise FileNotFoundError(f"缺少 {path}；请先运行 scripts/train_csp_lda.py")
    details = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    X_train, y_train, X_test, y_test, info = prepare_data()
    check_inputs(X_train, y_train, X_test, y_test, info)
    if details["channel_names"] != info["channel_names"] or details["sfreq_hz"] != info["sfreq"]:
        raise ValueError("保存的模型元数据与当前数据通道/采样率不一致")
    if details["epoch_samples"] != X_test.shape[2] or tuple(details["epoch_seconds_after_cue"]) != info["epoch_seconds"]:
        raise ValueError("保存的模型元数据与当前片段窗口不一致")
    if tuple(details["filter"]["low_high_hz"]) != info["filter_hz"]:
        raise ValueError("保存的模型滤波参数与当前数据不一致")
    if details["filter"]["order"] != info["filter_order"]:
        raise ValueError("保存的模型滤波阶数与当前数据不一致")
    if tuple(details["train_runs"]) != info["train_runs"] or details["test_run"] != info["test_run"]:
        raise ValueError("保存的模型记录划分与当前数据不一致")
    model = joblib.load(MODEL_PATH)
    saved_predictions = np.load(PREDICTIONS_PATH, allow_pickle=False)
    reloaded_predictions = model.predict(X_test)
    if not np.array_equal(saved_predictions, reloaded_predictions):
        raise RuntimeError("重新加载后的 R12 预测与保存前不同")
    print(f"重新加载预测一致：是（{len(reloaded_predictions)} 段）")
    print("R12 预测标签：" + ", ".join(map(str, reloaded_predictions.tolist())))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(f"加载核验失败：{error}")
