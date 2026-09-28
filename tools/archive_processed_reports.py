from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "待发布日报"
ARCHIVE = INBOX / "已发布"
LAST_FILES_FILE = ROOT / ".last-report-files.json"


def available_destination(source: Path) -> Path:
    destination = ARCHIVE / source.name
    if not destination.exists():
        return destination
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return ARCHIVE / f"{source.stem}_{stamp}{source.suffix}"


def main() -> int:
    try:
        if not LAST_FILES_FILE.exists():
            print("没有需要归档的日报文件。")
            return 0
        paths = json.loads(LAST_FILES_FILE.read_text(encoding="utf-8"))
        ARCHIVE.mkdir(parents=True, exist_ok=True)
        moved = 0
        for value in paths:
            source = Path(value).resolve()
            if not source.is_file() or source.parent != INBOX.resolve():
                continue
            shutil.move(str(source), str(available_destination(source)))
            moved += 1
        LAST_FILES_FILE.unlink(missing_ok=True)
        print(f"已归档 {moved} 个日报文件到：{ARCHIVE}")
        return 0
    except Exception as exc:
        print(f"归档失败：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
