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

DATA_FILE = ROOT / "dist" / "data" / "report-data.json"
WEB_OUTPUT = ROOT / "dist" / "images" / "reports"
VS_GROUPS = ["左娜组", "晶晶组"]


def build_report(payload: dict, report_date: str) -> dict:
    day = next((item for item in payload.get("days", []) if item.get("date") == report_date), None)
    if day is None:
        raise ValueError(f"网页数据中找不到 {report_date} 日报。")
    people = [row for row in day.get("personal", []) if row.get("bigGroup") in VS_GROUPS]
    people = rank_rows(people, "score")
    groups = []
    for name in VS_GROUPS:
        members = [row for row in people if row.get("bigGroup") == name]
        total = sum(int(row.get("score", 0)) for row in members)
        groups.append(
            {
                "name": name,
                "count": len(members),
                "avg": total / len(members) if members else 0,
            }
        )
    return {"people": people, "groups": groups}


def draw_group_card(draw: ImageDraw.ImageDraw, box: tuple, name: str, avg: float, count: int, winner: bool) -> None:
    x, y, w, h = box
    rounded(draw, (x, y, x + w, y + h), COLORS["paper"], 16, COLORS["teal"] if winner else None)
    draw.text((x + 24, y + 22), name, font=font(22, True), fill=COLORS["ink"])
    color = COLORS["teal"] if winner else COLORS["navy2"]
    draw.text((x + 24, y + 62), f"{avg:.2f}", font=font(56, True), fill=color)
    draw.text((x + 24, y + 136), f"人均积分 · {count}人", font=font(17), fill=COLORS["muted"])


def generate(report: dict, report_date: str) -> Image.Image:
    image = Image.new("RGB", (1242, 1180), COLORS["canvas"])
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1242, 278), fill=COLORS["navy"])
    draw.rectangle((0, 270, 1242, 278), fill=COLORS["teal"])
    draw.text((56, 42), "中国电信", font=font(20), fill="#b9c8d8")
    draw.text((56, 80), "左娜组 vs 晶晶组 PK日报", font=font(44, True), fill="#ffffff")
    year, month, day = report_date.split("-")
    draw.text((1186, 96), f"{year}年{int(month)}月{int(day)}日", font=font(26, True), fill="#ffffff", anchor="ra")
    draw.text((1186, 140), "大组人均积分PK · 个人积分排名", font=font(19), fill="#b9c8d8", anchor="ra")

    g1, g2 = report["groups"]
    winner1 = g1["avg"] >= g2["avg"]
    winner2 = g2["avg"] >= g1["avg"]
    card_w, card_h, y = 470, 200, 300
    draw_group_card(draw, (56, y, card_w, card_h), g1["name"], g1["avg"], g1["count"], winner1)
    draw.text((621, y + card_h // 2), "VS", font=font(40, True), fill=COLORS["muted"], anchor="mm")
    draw_group_card(draw, (716, y, card_w, card_h), g2["name"], g2["avg"], g2["count"], winner2)

    draw.text((56, 536), "计分口径：挽留成功 +1；失败 −1；质检 −1；人均分 = 大组累计积分 ÷ 人数。", font=font(18), fill=COLORS["muted"])
    draw_rank_section(draw, 576, "个人积分排名", report["people"], "personal")

    rounded(draw, (56, 990, 1186, 1056), COLORS["navy"], 14)
    draw.text((82, 1008), "左娜组 vs 晶晶组 PK通报", font=font(20, True), fill="#ffffff")
    draw.text((1160, 1008), SITE_URL, font=font(16), fill="#c9d6e2", anchor="ra")
    return image


def main() -> int:
    parser = argparse.ArgumentParser(description="生成左娜组 vs 晶晶组 PK日报图片。")
    parser.add_argument("--date", help="日报日期，格式 YYYY-MM-DD；默认取最新一天。")
    args = parser.parse_args()
    try:
        payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        dates = [item.get("date") for item in payload.get("days", [])]
        report_date = args.date or (sorted(dates)[-1] if dates else "")
        if not report_date:
            raise ValueError("没有可用的日报日期。")
        report = build_report(payload, report_date)
        if not report["people"]:
            raise ValueError("该日期没有左娜组或晶晶组的人员数据。")
        image = generate(report, report_date)
        LOCAL_OUTPUT.mkdir(parents=True, exist_ok=True)
        WEB_OUTPUT.mkdir(parents=True, exist_ok=True)
        local_path = LOCAL_OUTPUT / f"{report_date}_左娜PK晶晶.png"
        web_path = WEB_OUTPUT / f"vs-{report_date}.png"
        image.save(local_path, format="PNG", optimize=True)
        image.save(web_path, format="PNG", optimize=True)
        print(f"已生成左娜PK晶晶图片：{local_path}")
        return 0
    except Exception as exc:
        print(f"左娜PK晶晶图片生成失败：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
