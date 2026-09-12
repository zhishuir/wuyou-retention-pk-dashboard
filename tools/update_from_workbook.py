from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "dist" / "data" / "report-data.json"
INBOX = ROOT / "待发布日报"


def newest_workbook() -> Path:
    candidates = sorted(INBOX.glob("*.xlsx"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"请先把日报Excel放入：{INBOX}")
    return candidates[0]


def text(value: object) -> str:
    return "" if value is None else str(value).strip()


def integer(value: object) -> int:
    if value in (None, ""):
        return 0
    return int(float(value))


def read_day(workbook_path: Path) -> dict:
    if not workbook_path.is_file():
        raise FileNotFoundError(f"找不到日报文件：{workbook_path}")
    if workbook_path.suffix.lower() not in {".xlsx", ".xlsm"}:
        raise ValueError("日报文件必须是 .xlsx 或 .xlsm 格式。")

    workbook = load_workbook(workbook_path, data_only=True, read_only=True)
    if "计分明细" not in workbook.sheetnames:
        raise ValueError("工作簿缺少“计分明细”工作表。")

    sheet = workbook["计分明细"]
    people: list[dict] = []
    report_date = ""
    for row in sheet.iter_rows(min_row=4, values_only=True):
        if not text(row[3]):
            continue
        if not report_date:
            date_value = row[0]
            if isinstance(date_value, (date, datetime)):
                report_date = date_value.strftime("%Y-%m-%d")
            else:
                report_date = text(date_value)[:10]
        big_group = text(row[1]) or "待确认班组"
        small_group = text(row[2]) or "待确认小组"
        plus = integer(row[4])
        failure = integer(row[5])
        qc = integer(row[6])
        people.append(
            {
                "name": text(row[3]),
                "bigGroup": big_group,
                "smallGroup": small_group,
                "plus": plus,
                "failure": failure,
                "qc": qc,
                "score": plus - failure - qc,
                "matched": big_group != "待确认班组",
            }
        )

    if not report_date:
        raise ValueError("“计分明细”中没有可用日期。")
    if not people:
        raise ValueError("“计分明细”中没有人员数据。")
    return {"date": report_date, "personal": people}


def update_data(workbook_path: Path) -> tuple[str, int]:
    day = read_day(workbook_path)
    if DATA_FILE.exists():
        payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    else:
        payload = {"updatedAt": "", "days": []}
    days = [item for item in payload.get("days", []) if item.get("date") != day["date"]]
    days.append(day)
    days.sort(key=lambda item: item["date"])
    payload = {
        "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "days": days,
    }
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return day["date"], len(day["personal"])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="把日报 Excel 中的计分明细更新到网页数据文件。"
    )
    parser.add_argument(
        "workbook",
        nargs="?",
        type=Path,
        help="日报 Excel 路径；省略时读取“待发布日报”目录中最新的文件。",
    )
    args = parser.parse_args()
    try:
        workbook_path = args.workbook.resolve() if args.workbook else newest_workbook()
        report_date, people_count = update_data(workbook_path)
        print(f"已更新 {report_date} 日报，共 {people_count} 人。")
        return 0
    except Exception as exc:
        print(f"更新失败：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
