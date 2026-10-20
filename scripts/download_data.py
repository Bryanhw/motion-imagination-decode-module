"""Download only the three selected PhysioNet EDF files."""
from pathlib import Path
import time
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
BASE_URL = "https://physionet.org/files/eegmmidb/1.0.0/S001/"
FILES = ("S001R04.edf", "S001R08.edf", "S001R12.edf")
CHUNK_SIZE = 1024 * 1024
MAX_ATTEMPTS = 4


def download_one(session: requests.Session, filename: str) -> Path:
    """Fetch one file, resuming partial downloads and checking expected size."""
    destination = DATA_DIR / filename
    temporary = destination.with_suffix(destination.suffix + ".part")
    url = BASE_URL + filename

    for attempt in range(1, MAX_ATTEMPTS + 1):
        existing = temporary.stat().st_size if temporary.exists() else 0
        headers = {"Range": f"bytes={existing}-"} if existing else {}
        try:
            with session.get(url, headers=headers, stream=True, timeout=(20, 90)) as response:
                response.raise_for_status()
                if existing and response.status_code != 206:
                    # The server ignored Range, so restart instead of appending duplicate bytes.
                    existing = 0
                    mode = "wb"
                else:
                    mode = "ab" if existing else "wb"
                with temporary.open(mode) as output:
                    for chunk in response.iter_content(CHUNK_SIZE):
                        if chunk:
                            output.write(chunk)
                expected = response.headers.get("Content-Range", "").rsplit("/", 1)[-1]
                if not expected:
                    expected = response.headers.get("Content-Length")
                if expected and expected.isdigit() and temporary.stat().st_size != int(expected):
                    raise OSError(f"文件仍不完整：收到 {temporary.stat().st_size} / {expected} 字节")
                if temporary.stat().st_size < 1_000_000:
                    raise OSError(f"文件异常偏小：{temporary.stat().st_size:,} 字节；将重试")
                temporary.replace(destination)
                return destination
        except Exception:
            if attempt == MAX_ATTEMPTS:
                raise
            time.sleep(attempt * 2)
    raise RuntimeError("下载重试次数已用尽")


def main() -> int:
    DATA_DIR.mkdir(exist_ok=True)
    errors = []
    with requests.Session() as session:
        for filename in FILES:
            destination = DATA_DIR / filename
            temporary = destination.with_suffix(destination.suffix + ".part")
            if destination.exists() and destination.stat().st_size >= 1_000_000:
                print(f"已存在（大小正常），跳过：data/{filename} ({destination.stat().st_size:,} 字节)")
                continue
            if destination.exists():
                temporary.parent.mkdir(exist_ok=True)
                destination.replace(temporary)
                print(f"发现不完整文件，准备续传：data/{filename}")
            print(f"正在下载：{BASE_URL + filename}")
            try:
                result = download_one(session, filename)
                print(f"下载完成：data/{filename} ({result.stat().st_size:,} 字节)")
            except Exception as exc:
                errors.append(filename)
                print(f"下载失败：{filename}: {type(exc).__name__}: {exc}")
                temporary.unlink(missing_ok=True)
    if errors:
        print("\n部分文件未下载。可按 README.md 中的直链手动下载到 data/ 后重试。")
        return 1
    print("\n指定的三份 EDF 均已存在或下载完成；没有下载其他数据集文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
