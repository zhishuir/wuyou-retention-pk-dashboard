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
    font,
    rank_rows,
    rounded,
)

DATA_FILE = ROOT / "dist" / "data" / "report-data.json"
WEB_OUTPUT = ROOT / "dist" / "images" / "reports"
VS_GROUPS = ["左娜组", "晶晶组"]


def build_report(payload: dict, report_date: str) -> list[dict]:
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
                "members": members,
                "count": len(members),
                "avg": total / len(members) if members else 0,
            }
        )
    return groups


def draw_member_list(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, group: dict) -> None:
    rounded(draw, (x, y, x + w, y + 86), COLORS["paper"], 14, COLORS["line"])
    draw.text((x + 22, y + 18), group["name"], font=font(24, True), fill=COLORS["ink"])
    draw.text((x + w - 22, y + 20), f"人均 {group['avg']:.2f}", font=font(22, True), fill=COLORS["teal"], anchor="ra")
    draw.text((x + 22, y + 54), f"{group['count']}人", font=font(15), fill=COLORS["muted"])

    row_y = y + 98
    for i, member in enumerate(group["members"]):
        ry = row_y + i * 48
        if i % 2 == 0:
            rounded(draw, (x, ry, x + w, ry + 40), COLORS["paper"], 8)
        draw.text((x + 16, ry + 8), str(i + 1), font=font(18, True), fill=COLORS["muted"])
        draw.text((x + 52, ry + 8), member["name"], font=font(20, True), fill=COLORS["ink"])
        score = member["score"]
        color = COLORS["teal"] if score > 0 else COLORS["red"] if score < 0 else COLORS["muted"]
        draw.text((x + w - 18, ry + 8), str(score), font=font(20, True), fill=color, anchor="ra")


def generate(groups: list[dict], report_date: str) -> Image.Image:
    image = Image.new("RGB", (1242, 1020), COLORS["canvas"])
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1242, 278), fill=COLORS["navy"])
    draw.rectangle((0, 270, 1242, 278), fill=COLORS["teal"])
    draw.text((56, 42), "中国电信", font=font(20), fill="#b9c8d8")
    draw.text((56, 80), "左娜组 vs 晶晶组 PK日报", font=font(44, True), fill="#ffffff")
    year, month, day = report_date.split("-")
    draw.text((1186, 96), f"{year}年{int(month)}月{int(day)}日", font=font(26, True), fill="#ffffff", anchor="ra")
    draw.text((1186, 140), "两组成员积分排名", font=font(19), fill="#b9c8d8", anchor="ra")

    col_w = 550
    y = 310
    draw_member_list(draw, 56, y, col_w, groups[0])
    draw_member_list(draw, 56 + col_w + 30, y, col_w, groups[1])

    rounded(draw, (56, 910, 1186, 976), COLORS["navy"], 14)
    draw.text((82, 928), "左娜组 vs 晶晶组 PK通报", font=font(20, True), fill="#ffffff")
    draw.text((1160, 928), SITE_URL, font=font(16), fill="#c9d6e2", anchor="ra")
    return image


def main() -> int:
    parser = argparse.ArgumentParser(description="生成左娜组 vs 晶晶组 PK日报图片。")
    parser.add_argument(
        "--date",
        action="append",
        help="日报日期，格式 YYYY-MM-DD；可重复填写。默认生成本次导入的全部日期。",
    )
    args = parser.parse_args()
    try:
        payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        dates = [item.get("date") for item in payload.get("days", [])]
        if args.date:
            report_dates = args.date
        else:
            report_dates = dates
        report_dates = list(dict.fromkeys(report_dates))
        if not report_dates:
            raise ValueError("没有可用的日报日期。")
        LOCAL_OUTPUT.mkdir(parents=True, exist_ok=True)
        WEB_OUTPUT.mkdir(parents=True, exist_ok=True)
        generated = 0
        for report_date in report_dates:
            groups = build_report(payload, report_date)
            if not groups or not groups[0]["members"]:
                raise ValueError(f"{report_date} 没有左娜组或晶晶组的人员数据。")
            image = generate(groups, report_date)
            local_path = LOCAL_OUTPUT / f"{report_date}_左娜PK晶晶.png"
            web_path = WEB_OUTPUT / f"vs-{report_date}.png"
            image.save(local_path, format="PNG", optimize=True)
            image.save(web_path, format="PNG", optimize=True)
            generated += 1
            print(f"已生成左娜PK晶晶图片：{local_path}")
        print(f"左娜PK晶晶日报图片生成完成，共 {generated} 张。")
        return 0
    except Exception as exc:
        print(f"左娜PK晶晶图片生成失败：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
