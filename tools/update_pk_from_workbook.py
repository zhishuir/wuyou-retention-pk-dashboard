from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
PK_DATA_FILE = ROOT / "dist" / "data" / "pk-data.json"
RETENTION_DATA_FILE = ROOT / "dist" / "data" / "report-data.json"
INBOX = ROOT / "待发布PK"
SUPPORTED_SUFFIXES = {".xlsx", ".xlsm"}


def text(value: object) -> str:
    return "" if value is None else str(value).strip()


def newest_workbook() -> Path:
    candidates = (
        sorted(
            (path for path in INBOX.iterdir() if path.suffix.lower() in SUPPORTED_SUFFIXES),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if INBOX.exists()
        else []
    )
    if not candidates:
        raise FileNotFoundError(f"请先把营销PK赛模板放入：{INBOX}")
    return candidates[0]


def read_project_scores(workbook) -> list[dict]:
    if "项目分值" not in workbook.sheetnames:
        raise ValueError("模板中缺少「项目分值」工作表。")
    sheet = workbook["项目分值"]
    scores: list[dict] = []
    seen: set[str] = set()
    for row in sheet.iter_rows(min_row=2, max_col=2, values_only=True):
        name = text(row[0])
        if not name:
            continue
        try:
            score = int(float(row[1]))
        except (TypeError, ValueError):
            raise ValueError(f"「项目分值」表中项目“{name}”的分值不是数字。") from None
        if score <= 0:
            raise ValueError(f"「项目分值」表中项目“{name}”的分值必须大于 0。")
        if name in seen:
            raise ValueError(f"「项目分值」表中项目“{name}”重复。")
        seen.add(name)
        scores.append({"name": name, "score": score})
    if not scores:
        raise ValueError("「项目分值」表为空，请先填写项目和分值。")
    return scores


def read_records(workbook, project_scores: list[dict]) -> tuple[dict[str, dict[str, int]], set[str]]:
    if "加分记录" not in workbook.sheetnames:
        raise ValueError("模板中缺少「加分记录」工作表。")
    sheet = workbook["加分记录"]
    score_map = {item["name"]: item["score"] for item in project_scores}
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    unknown_projects: set[str] = set()
    for row in sheet.iter_rows(min_row=2, max_col=3, values_only=True):
        name = text(row[1])
        project = text(row[2])
        if not name or not project:
            continue
        if project not in score_map:
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


def build_personal(counts: dict, project_scores: list[dict], roster: dict) -> list[dict]:
    score_map = {item["name"]: item["score"] for item in project_scores}
    people: list[dict] = []
    for name, detail in counts.items():
        total = sum(count * score_map[project] for project, count in detail.items())
        membership = roster.get(name)
        people.append(
            {
                "name": name,
                "bigGroup": membership["bigGroup"] if membership else "待确认班组",
                "smallGroup": membership["smallGroup"] if membership else "待确认小组",
                "matched": membership is not None,
                "occurrences": sum(detail.values()),
                "score": total,
                "detail": dict(sorted(detail.items())),
            }
        )
    people.sort(key=lambda person: (-person["score"], -person["occurrences"], person["name"]))
    for index, person in enumerate(people):
        person["rank"] = index + 1
    return people


def update_data(workbook_path: Path, data_file: Path = PK_DATA_FILE) -> dict:
    workbook = load_workbook(workbook_path, data_only=True, read_only=True)
    project_scores = read_project_scores(workbook)
    counts, unknown_projects = read_records(workbook, project_scores)
    if unknown_projects:
        print("警告：以下项目不在「项目分值」表中，已忽略：" + "、".join(sorted(unknown_projects)))
    roster = roster_from_retention()
    personal = build_personal(counts, project_scores, roster)
    payload = {
        "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "projectScores": project_scores,
        "personal": personal,
    }
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    unmatched = [person["name"] for person in personal if not person["matched"]]
    return {
        "projects": len(project_scores),
        "people": len(personal),
        "total": sum(person["score"] for person in personal),
        "unmatched": unmatched,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="把营销PK赛模板更新到网页数据文件。")
    parser.add_argument(
        "workbook",
        nargs="?",
        type=Path,
        help="模板 Excel 路径；省略时读取“待发布PK”目录中最新的文件。",
    )
    parser.add_argument("--data-file", type=Path, default=PK_DATA_FILE, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        workbook_path = args.workbook.resolve() if args.workbook else newest_workbook()
        summary = update_data(workbook_path, args.data_file.resolve())
        print(
            f"已更新营销PK赛：{summary['projects']} 个项目，"
            f"{summary['people']} 人参赛，累计加分 {summary['total']} 分。"
        )
        if summary["unmatched"]:
            print("待确认名单：" + "、".join(summary["unmatched"]))
        return 0
    except Exception as exc:
        print(f"PK赛更新失败：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
