"""Shared labels for the unilateral fist imagery runs (R04/R08/R12)."""

LABELS = {"T1": "左手想象", "T2": "右手想象"}


def imagery_events(raw):
    """Return T1/T2 event rows and their MNE event IDs."""
    import mne

    events, event_id = mne.events_from_annotations(raw, verbose="ERROR")
    missing = [code for code in LABELS if code not in event_id]
    if missing:
        raise ValueError(f"缺少任务标记：{', '.join(missing)}")
    wanted = {code: event_id[code] for code in LABELS}
    selected = events[[row[2] in wanted.values() for row in events]]
    return selected, wanted
