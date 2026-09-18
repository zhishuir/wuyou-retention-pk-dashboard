from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from generate_daily_image import DATA_FILE, LOCAL_OUTPUT, WEB_OUTPUT, generate, rank_rows


def week_bounds(anchor: date) -> tuple[date, date]:
    """自然周：周一到周日。"""
    monday = anchor - timedelta(days=anchor.weekday())
    return monday, monday + timedelta(days=6)


def week_key(start: date, end: date) -> str:
    return f"{start.isoformat()}~{end.isoformat()}"


def range_label(start: date, end: date) -> str:
    start_text = f"{start.year}年{start.month:02d}月{start.day:02d}日"
    if start.year != end.year:
        end_text = f"{end.year}年{end.month:02d}月{end.day:02d}日"
    else:
        end_text = f"{end.month:02d}月{end.day:02d}日"
    return f"{start_text} — {end_text}"


def aggregate_week(payload: dict, start: date, end: date) -> dict:
    days = [
        item
        for item in payload.get("days", [])
        if start <= date.fromisoformat(item["date"]) <= end
    ]
    if not days:
        raise ValueError(f"{week_key(start, end)} 这一周还没有日报数据。")

    registry: dict[str, dict] = {}
    for day in days:
        for row in day.get("personal", []):
            name = (row.get("name") or "").strip()
            if not name:
                continue
            if name not in registry:
                registry[name] = {
                    "name": name,
                    "bigGroup": row.get("bigGroup") or "待确认班组",
                    "smallGroup": row.get("smallGroup") or "待确认小组",
                    "matched": row.get("matched") is not False
                    and (row.get("bigGroup") or "待确认班组") != "待确认班组",
                    "plus": 0,
                    "failure": 0,
                    "qc": 0,
                    "score": 0,
                }
            person = registry[name]
            person["bigGroup"] = row.get("bigGroup") or person["bigGroup"]
            person["smallGroup"] = row.get("smallGroup") or person["smallGroup"]
            person["matched"] = row.get("matched") is not False and person["bigGroup"] != "待确认班组"
            plus = int(row.get("plus") or 0)
            failure = int(row.get("failure") or 0)
            qc = int(row.get("qc") or 0)
            person["plus"] += plus
            person["failure"] += failure
            person["qc"] += qc
            person["score"] += int(
                row.get("score") if row.get("score") is not None else plus - failure - qc
            )

    personal = rank_rows(list(registry.values()), "score")
    matched = [row for row in personal if row.get("matched") and row.get("bigGroup") != "待确认班组"]

    def group_rows(field: str) -> list[dict]:
        groups: dict[str, dict] = {}
        for row in matched:
            name = row[field]
            if name not in groups:
                groups[name] = {
                    "name": name,
                    "bigGroup": row.get("bigGroup", ""),
                    "members": set(),
                    "plus": 0,
                    "failure": 0,
                    "qc": 0,
                    "score": 0,
                }
            group = groups[name]
            group["members"].add(row["name"])
            for key in ("plus", "failure", "qc", "score"):
                group[key] += int(row.get(key, 0))
        result = []
        for group in groups.values():
            headcount = len(group.pop("members"))
            result.append(
                {
                    **group,
                    "headcount": headcount,
                    "average": group["score"] / headcount if headcount else 0,
                }
            )
        return rank_rows(result, "average")

    return {
        "date": week_key(start, end),
        "personal": personal,
        "small": group_rows("smallGroup"),
        "big": group_rows("bigGroup"),
        "plus": sum(int(row.get("plus", 0)) for row in personal),
        "failure": sum(int(row.get("failure", 0)) for row in personal),
        "qc": sum(int(row.get("qc", 0)) for row in personal),
        "score": sum(int(row.get("score", 0)) for row in personal),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成降档低签挽留周报PNG图片。")
    parser.add_argument(
        "--date",
        help="锚定日期，格式 YYYY-MM-DD；默认今天，按自然周（周一~周日）聚合。",
    )
    args = parser.parse_args()
    try:
        anchor = date.fromisoformat(args.date) if args.date else date.today()
        start, end = week_bounds(anchor)
        payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        report = aggregate_week(payload, start, end)
        image = generate(
            report,
            title="降档低签挽留周报",
            date_text=range_label(start, end),
            total_unit="本周",
        )
        LOCAL_OUTPUT.mkdir(parents=True, exist_ok=True)
        WEB_OUTPUT.mkdir(parents=True, exist_ok=True)
        local_path = LOCAL_OUTPUT / f"{report['date']}_降档低签挽留周报.png"
        web_path = WEB_OUTPUT / f"{report['date']}.png"
        image.save(local_path, format="PNG", optimize=True)
        image.save(web_path, format="PNG", optimize=True)
        print(f"已生成周报图片：{local_path}（{start.isoformat()} ~ {end.isoformat()}）")
        return 0
    except Exception as exc:
        print(f"周报生成失败：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
