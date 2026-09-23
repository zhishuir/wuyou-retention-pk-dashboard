from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

from generate_daily_image import (
    COLORS,
    ROOT,
    LOCAL_OUTPUT,
    SITE_URL,
    draw_rank_section,
    font,
    rank_rows,
    rounded,
)

# 营销PK赛专用配色（区别于挽留考核的蓝绿主题）
COLORS.update(
    {
        "navy": "#005BAC",  # 中国电信蓝
        "navy2": "#003E7E",
        "teal": "#E8840C",  # 橙色主强调
        "teal_soft": "#FFF0DC",
    }
)

DATA_FILE = ROOT / "dist" / "data" / "pk-data.json"
WEB_OUTPUT = ROOT / "dist" / "images" / "reports"


def group_rows(matched: list[dict], field: str) -> list[dict]:
    groups: dict[str, dict] = {}
    for row in matched:
        name = row[field]
        if name not in groups:
            groups[name] = {
                "name": name,
                "bigGroup": row.get("bigGroup", ""),
                "members": set(),
                "score": 0,
            }
        group = groups[name]
        group["members"].add(row["name"])
        group["score"] += int(row.get("score", 0))
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


def build_report(payload: dict) -> dict:
    personal = rank_rows(list(payload.get("personal", [])), "score")
    matched = [row for row in personal if row.get("matched") and row.get("bigGroup") != "待确认班组"]
    projects: set[str] = set()
    for row in personal:
        projects.update((row.get("detail") or {}).keys())
    return {
        "personal": personal,
        "small": group_rows(matched, "smallGroup"),
        "big": group_rows(matched, "bigGroup"),
        "total": sum(int(row.get("score", 0)) for row in personal),
        "people": len(personal),
        "projects": len(projects),
        "top": personal[0]["score"] if personal else 0,
    }


def generate(report: dict, report_date: str) -> Image.Image:
    image = Image.new("RGB", (1242, 2000), COLORS["canvas"])
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1242, 278), fill=COLORS["navy"])
    draw.rectangle((0, 270, 1242, 278), fill=COLORS["teal"])
    draw.text((56, 42), "中国电信", font=font(20), fill="#b9c8d8")
    draw.text((56, 80), "营销PK赛日报", font=font(50, True), fill="#ffffff")
    year, month, day = report_date.split("-")
    draw.text((1186, 96), f"{year}年{int(month)}月{int(day)}日", font=font(26, True), fill="#ffffff", anchor="ra")
    draw.text((1186, 140), "个人、小组及大组积分排名", font=font(19), fill="#b9c8d8", anchor="ra")

    kpis = [
        ("累计总加分", report["total"], COLORS["teal"], "分"),
        ("参赛人数", report["people"], COLORS["navy2"], "人"),
        ("加分项目", report["projects"], COLORS["amber"], "个"),
        ("最高个人积分", report["top"], COLORS["navy2"], "分"),
    ]
    card_width, gap, y = 270, 16, 208
    for index, (label, value, accent, unit) in enumerate(kpis):
        x = 56 + index * (card_width + gap)
        rounded(draw, (x, y, x + card_width, y + 154), COLORS["paper"], 16)
        draw.rectangle((x, y, x + 6, y + 154), fill=accent)
        draw.text((x + 24, y + 20), label, font=font(19, True), fill=COLORS["muted"])
        draw.text((x + 24, y + 55), str(value), font=font(45, True), fill=COLORS["ink"])
        draw.text((x + 24, y + 119), unit, font=font(15), fill=COLORS["muted"])

    draw.text((56, 396), "计分口径：只加分不扣分，不同项目分值固定。", font=font(18), fill=COLORS["muted"])
    draw_rank_section(draw, 452, "个人积分排名", report["personal"], "personal")
    draw_rank_section(draw, 856, "小组人均积分排名", report["small"], "small")
    draw_rank_section(draw, 1260, "大组人均积分排名", report["big"], "big")

    draw.line((56, 1714, 1186, 1714), fill=COLORS["line"], width=2)
    draw.text((56, 1744), "说明", font=font(22, True), fill=COLORS["ink"])
    draw.text((56, 1786), "小组、大组按参赛人数计算人均分；待确认人员不计入班组均分。", font=font(18), fill=COLORS["muted"])
    draw.text((56, 1822), "完整排名请查看网页报表。", font=font(18), fill=COLORS["muted"])
    rounded(draw, (56, 1874, 1186, 1940), COLORS["navy"], 14)
    draw.text((82, 1892), "营销PK赛排名通报", font=font(20, True), fill="#ffffff")
    draw.text((1160, 1892), SITE_URL, font=font(16), fill="#c9d6e2", anchor="ra")
    return image


def main() -> int:
    parser = argparse.ArgumentParser(description="生成营销PK赛日报PNG图片。")
    parser.add_argument("--date", help="日报日期，格式 YYYY-MM-DD；默认读取刚导入的日期。")
    args = parser.parse_args()
    try:
        payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        report_date = args.date or (payload.get("date") or "")
        if not report_date:
            raise ValueError("没有找到日报日期。")
        report = build_report(payload)
        image = generate(report, report_date)
        LOCAL_OUTPUT.mkdir(parents=True, exist_ok=True)
        WEB_OUTPUT.mkdir(parents=True, exist_ok=True)
        local_path = LOCAL_OUTPUT / f"{report_date}_营销PK赛.png"
        web_path = WEB_OUTPUT / f"pk-{report_date}.png"
        image.save(local_path, format="PNG", optimize=True)
        image.save(web_path, format="PNG", optimize=True)
        print(f"已生成营销PK赛图片：{local_path}")
        return 0
    except Exception as exc:
        print(f"PK赛图片生成失败：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
