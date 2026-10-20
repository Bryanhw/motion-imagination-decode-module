from pathlib import Path
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
BASE_URL = "https://physionet.org/files/eegmmidb/1.0.0/S001/"
FILES = ("S001R04.edf", "S001R08.edf", "S001R12.edf")


def main() -> int:
    DATA_DIR.mkdir(exist_ok=True)
    errors = []
    for filename in FILES:
        destination = DATA_DIR / filename
        if destination.exists() and destination.stat().st_size > 0:
            print(f"已存在，跳过：{destination.relative_to(PROJECT_ROOT)} ({destination.stat().st_size:,} 字节)")
            continue
        url = BASE_URL + filename
        temporary = destination.with_suffix(destination.suffix + ".part")
        print(f"正在下载：{url}")
        try:
            with urlopen(url, timeout=60) as response, temporary.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
            if temporary.stat().st_size == 0:
                raise OSError("服务器返回了空文件")
            temporary.replace(destination)
            print(f"下载完成：{destination.relative_to(PROJECT_ROOT)} ({destination.stat().st_size:,} 字节)")
        except Exception as exc:
            temporary.unlink(missing_ok=True)
            message = f"{filename}: {type(exc).__name__}: {exc}"
            errors.append(message)
            print(f"下载失败：{message}")
    if errors:
        print("\n部分文件未下载。可按 README.md 中的直链手动下载到 data/ 后重试。")
        return 1
    print("\n指定的三份 EDF 均已存在或下载完成；没有下载其他数据集文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

