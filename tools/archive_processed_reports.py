from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "待发布日报"
ARCHIVE = INBOX / "已发布"
LAST_FILES_FILE = ROOT / ".last-report-files.json"
PK_INBOX = ROOT / "待发布PK"
PK_ARCHIVE = PK_INBOX / "已发布"
LAST_PK_FILES_FILE = ROOT / ".last-pk-files.json"


def available_destination(source: Path, archive: Path) -> Path:
    destination = archive / source.name
    if not destination.exists():
        return destination
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return archive / f"{source.stem}_{stamp}{source.suffix}"


def archive_files(marker: Path, inbox: Path, archive: Path, label: str) -> int:
    if not marker.exists():
        print(f"没有需要归档的{label}文件。")
        return 0
    paths = json.loads(marker.read_text(encoding="utf-8"))
    archive.mkdir(parents=True, exist_ok=True)
    moved = 0
    for value in paths:
        source = Path(value).resolve()
        if not source.is_file() or source.parent != inbox.resolve():
            continue
        shutil.move(str(source), str(available_destination(source, archive)))
        moved += 1
    marker.unlink(missing_ok=True)
    print(f"已归档 {moved} 个{label}文件到：{archive}")
    return moved


def main() -> int:
    try:
        archive_files(LAST_FILES_FILE, INBOX, ARCHIVE, "挽留日报")
        archive_files(LAST_PK_FILES_FILE, PK_INBOX, PK_ARCHIVE, "营销日报")
        return 0
    except Exception as exc:
        print(f"归档失败：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
