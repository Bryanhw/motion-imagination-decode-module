# -*- coding: utf-8 -*-
"""RA1 复验探针：用 venv python 进程尝试写 bci-decoder/artifacts/users/<probe>/。
工程自检用，仅创建后再删除，不留残留。不报任何精度/性能。
目标路径 = 仓库 <bci-decoder>/artifacts/users/
"""
import sys, pathlib, datetime, shutil

bci = pathlib.Path(__file__).resolve().parents[1]  # <repo>/bci-decoder
art = bci / "artifacts"
probe = art / "users" / "ra1_probe"
fail = False
try:
    probe.mkdir(parents=True, exist_ok=True)
    f = probe / "probe.txt"
    f.write_text("RA1 probe " + datetime.datetime.now().isoformat() + "\n", encoding="utf-8")
    ok = f.exists()
    print("TARGET=%s" % probe)
    print("WRITE_OK=%s file=%s" % (ok, f))
except Exception as e:
    fail = True
    print("TARGET=%s" % probe)
    print("WRITE_FAIL=%r" % (e,))
finally:
    # 清理探针残留（含可能存在的错误父目录）
    shutil.rmtree(probe, ignore_errors=True)
    bad = bci / "scripts" / "artifacts"
    if bad.exists():
        shutil.rmtree(bad, ignore_errors=True)
print("PY=%s" % sys.executable)
print("EXIT=%s" % ("FAIL" if fail else "OK"))
sys.exit(1 if fail else 0)
