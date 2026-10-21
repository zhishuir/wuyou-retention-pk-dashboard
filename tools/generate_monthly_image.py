"""按自然月汇总挽留考核，并生成网页可下载的月报图片。"""

from __future__ import annotations

import argparse
import calendar
import json
from datetime import date

from generate_daily_image import DATA_FILE, LOCAL_OUTPUT, WEB_OUTPUT, generate
from generate_weekly_image import aggregate_week


def generate_months(payload: dict, months: list[str] | None = None) -> int:
    available = sorted({day["date"][:7] for day in payload.get("days", [])})
    selected = months or available
    if not selected:
        raise ValueError("没有可生成的挽留月报数据。")
    LOCAL_OUTPUT.mkdir(parents=True, exist_ok=True)
    WEB_OUTPUT.mkdir(parents=True, exist_ok=True)
    for month in dict.fromkeys(selected):
        year, month_number = (int(part) for part in month.split("-"))
        start = date(year, month_number, 1)
        end = date(year, month_number, calendar.monthrange(year, month_number)[1])
        report = aggregate_week(payload, start, end)
        report["date"] = month
        image = generate(
            report,
            title="降档低签挽留月报",
            date_text=f"{year}年{month_number}月",
            total_unit="本月",
        )
        image.save(LOCAL_OUTPUT / f"{month}_降档低签挽留月报.png", format="PNG", optimize=True)
        image.save(WEB_OUTPUT / f"month-{month}.png", format="PNG", optimize=True)
    return len(list(dict.fromkeys(selected)))


def main() -> int:
    parser = argparse.ArgumentParser(description="生成降档低签挽留月报PNG图片。")
    parser.add_argument("--month", action="append", help="月份 YYYY-MM；默认生成全部有数据的月份。")
    args = parser.parse_args()
    try:
        payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        count = generate_months(payload, args.month)
        print(f"挽留月报图片生成完成，共 {count} 张。")
        return 0
    except Exception as exc:
        print(f"挽留月报生成失败：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
