from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
PK_DATA_FILE = ROOT / "dist" / "data" / "pk-data.json"
RETENTION_DATA_FILE = ROOT / "dist" / "data" / "report-data.json"
INBOX = ROOT / "待发布PK"
LAST_DATE_FILE = ROOT / ".last-pk-date"
LAST_FILES_FILE = ROOT / ".last-pk-files.json"
SUPPORTED_SUFFIXES = {".xlsx", ".xlsm"}

NAME_HEADERS = ("姓名", "人名")
PROJECT_HEADERS = ("项目", "项目名称")

# 项目分值固定表：只加分不扣分，不同项目分值不同。
# 新增/调整项目时，在这里修改即可，模板里不需要再填分值。
PROJECT_SCORES: dict[str, int] = {
    "20元20G-7天提速流量包": 1,
    "30元30G-7天提速流量包": 1,
    "9.9元权益包": 1,
    "35元20G连续包月流量包（首月19.9元）": 2,
    "15元10G包月流量包": 2,
    "套餐高迁": 4,
    "天翼智铃基础版": 1,
}

# 项目别名：业务上同义的项目名，统一归并到主项目计分。
PROJECT_ALIASES: dict[str, str] = {
    "高改套餐": "套餐高迁",
}


def text(value: object) -> str:
    return "" if value is None else str(value).strip()


def inbox_workbooks() -> list[Path]:
    candidates = [
        path
        for path in INBOX.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    ] if INBOX.exists() else []
    if not candidates:
        raise FileNotFoundError(f"请先把营销PK赛模板放入：{INBOX}")
    return sorted(
        candidates,
        key=lambda path: (parse_date_from_filename(path), path.stat().st_mtime, path.name),
    )


def parse_date_from_filename(path: Path) -> str:
    patterns = (
        r"(?<!\d)(20\d{2})[年._-](\d{1,2})[月._-](\d{1,2})日?(?!\d)",
        r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)",
    )
    for pattern in patterns:
        match = re.search(pattern, path.stem)
        if match:
            year, month, day = (int(part) for part in match.groups())
            return date(year, month, day).isoformat()
    raise ValueError(
        "营销日报文件名中缺少日期。请命名为“2026-09-22营销日报.xlsx”。"
    )


def read_records(workbook) -> tuple[dict, set[str]]:
    if "加分记录" not in workbook.sheetnames:
        raise ValueError("模板中缺少「加分记录」工作表。")
    sheet = workbook["加分记录"]

    header_row = next(sheet.iter_rows(min_row=1, max_row=1, max_col=3, values_only=True), None)
    headers = [text(cell) for cell in (header_row or [])]
    index = {"name": -1, "project": -1}
    for position, header in enumerate(headers):
        if header in NAME_HEADERS and index["name"] == -1:
            index["name"] = position
        elif header in PROJECT_HEADERS and index["project"] == -1:
            index["project"] = position
    if -1 in index.values():
        raise ValueError("表头需包含「姓名」和「项目」两列。")

    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    unknown_projects: set[str] = set()
    for row in sheet.iter_rows(min_row=2, max_col=max(index.values()) + 1, values_only=True):
        name = text(row[index["name"]])
        project = text(row[index["project"]])
        if not name:
            continue
        if not project:
            continue
        project = PROJECT_ALIASES.get(project, project)
        if project not in PROJECT_SCORES:
            unknown_projects.add(project)
            continue
        counts[name][project] += 1
    return dict(counts), unknown_projects


def roster_from_retention() -> dict[str, dict]:
    payload = json.loads(RETENTION_DATA_FILE.read_text(encoding="utf-8"))
    excluded = {text(name) for name in payload.get("excluded", []) if text(name)}
    roster: dict[str, dict] = {}
    for person in payload.get("roster", []):
        name = text(person.get("name"))
        if name and name not in excluded:
            roster[name] = {
                "name": name,
                "bigGroup": text(person.get("bigGroup")) or "待确认班组",
                "smallGroup": text(person.get("smallGroup")) or "待确认小组",
            }
    return roster


def excluded_names() -> set[str]:
    payload = json.loads(RETENTION_DATA_FILE.read_text(encoding="utf-8"))
    return {text(name) for name in payload.get("excluded", []) if text(name)}


def build_personal(counts: dict, roster: dict) -> list[dict]:
    people: list[dict] = []
    for name, detail in counts.items():
        total = sum(count * PROJECT_SCORES[project] for project, count in detail.items())
        membership = roster.get(name)
        people.append(
            {
                "name": name,
                "bigGroup": membership["bigGroup"] if membership else "待确认班组",
                "smallGroup": membership["smallGroup"] if membership else "待确认小组",
                "matched": membership is not None,
                "score": total,
                "detail": dict(sorted(detail.items())),
            }
        )
    people.sort(key=lambda person: (-person["score"], person["name"]))
    for index, person in enumerate(people):
        person["rank"] = index + 1
    return people


def build_project_scores() -> list[dict]:
    return [
        {"name": name, "score": score}
        for name, score in sorted(PROJECT_SCORES.items(), key=lambda item: (-item[1], item[0]))
    ]


def aggregate_personal(days: list[dict], roster: dict[str, dict]) -> list[dict]:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for day in days:
        for person in day.get("personal", []):
            name = text(person.get("name"))
            if not name:
                continue
            for project, count in (person.get("detail") or {}).items():
                if project in PROJECT_SCORES:
                    counts[name][project] += int(count)
    return build_personal(dict(counts), roster)


def update_data(workbook_path: Path, data_file: Path = PK_DATA_FILE) -> dict:
    workbook = load_workbook(workbook_path, data_only=True, read_only=True)
    counts, unknown_projects = read_records(workbook)
    roster = roster_from_retention()
    excluded = excluded_names()
    counts = {name: detail for name, detail in counts.items() if name not in excluded}
    if not counts:
        raise ValueError("「加分记录」表中没有有效数据。")
    report_date = parse_date_from_filename(workbook_path)
    day_personal = build_personal(counts, roster)
    if data_file.exists():
        existing = json.loads(data_file.read_text(encoding="utf-8"))
    else:
        existing = {}
    days = [item for item in existing.get("days", []) if item.get("date") != report_date]
    days.append({"date": report_date, "personal": day_personal})
    days.sort(key=lambda item: item["date"])
    personal = aggregate_personal(days, roster)
    payload = {
        "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "date": days[-1]["date"],
        "projectScores": build_project_scores(),
        "days": days,
        "personal": personal,
    }
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    unmatched = [person["name"] for person in day_personal if not person["matched"]]
    return {
        "date": report_date,
        "people": len(day_personal),
        "total": sum(person["score"] for person in day_personal),
        "unmatched": unmatched,
        "unknown_projects": sorted(unknown_projects),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="把营销PK赛模板(姓名+项目)更新到网页数据文件。")
    parser.add_argument(
        "workbooks",
        nargs="*",
        type=Path,
        help="模板 Excel 路径；省略时按日期读取“待发布PK”目录中的全部文件。",
    )
    parser.add_argument("--data-file", type=Path, default=PK_DATA_FILE, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        workbook_paths = (
            [path.resolve() for path in args.workbooks]
            if args.workbooks
            else inbox_workbooks()
        )
        workbook_paths.sort(key=lambda path: (parse_date_from_filename(path), path.name))
        summaries = []
        processed_paths = []
        failures = []
        data_file = args.data_file.resolve()
        for workbook_path in workbook_paths:
            try:
                summary = update_data(workbook_path, data_file)
            except Exception as exc:
                if args.workbooks:
                    raise
                failures.append((workbook_path, str(exc)))
                print(f"[跳过] {workbook_path.name}：{exc}")
                continue
            summaries.append(summary)
            processed_paths.append(workbook_path)
            print(
                f"已更新营销PK赛（{summary['date']}）：{summary['people']} 人参赛，"
                f"当日加分 {summary['total']} 分。"
            )
            if summary["unknown_projects"]:
                print(
                    "警告：以下项目不在固定分值表中，已忽略："
                    + "、".join(summary["unknown_projects"])
                )
            if summary["unmatched"]:
                print("待确认名单：" + "、".join(summary["unmatched"]))

        if not summaries:
            raise ValueError("没有成功导入任何营销日报文件，请检查上方错误提示。")
        if data_file == PK_DATA_FILE.resolve():
            report_dates = list(dict.fromkeys(summary["date"] for summary in summaries))
            LAST_DATE_FILE.write_text("\n".join(report_dates), encoding="utf-8")
            LAST_FILES_FILE.write_text(
                json.dumps(
                    [str(path.resolve()) for path in processed_paths],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        print(
            f"营销日报批量导入完成：成功 {len(summaries)} 个，"
            f"跳过 {len(failures)} 个。"
        )
        if failures:
            print("未处理文件会保留在“待发布PK”文件夹，请修复后再次运行。")
        return 0
    except Exception as exc:
        print(f"PK赛更新失败：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
