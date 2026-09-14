from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "dist" / "data" / "report-data.json"
LAST_DATE_FILE = ROOT / ".last-report-date"
LOCAL_OUTPUT = ROOT / "通报图片"
WEB_OUTPUT = ROOT / "dist" / "images" / "reports"
SITE_URL = "zhishuir.github.io/wuyou-retention-pk-dashboard"

COLORS = {
    "canvas": "#eef2f5",
    "paper": "#ffffff",
    "navy": "#112b46",
    "navy2": "#173e63",
    "teal": "#138a7a",
    "teal_soft": "#e2f4f0",
    "red": "#b64032",
    "red_soft": "#fbe9e5",
    "amber": "#d39528",
    "ink": "#152437",
    "muted": "#64748b",
    "line": "#d9e1e8",
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def score_key(row: dict, metric: str) -> tuple:
    return (
        -float(row[metric]),
        -int(row["plus"]),
        int(row["failure"]),
        int(row["qc"]),
        str(row["name"]),
    )


def rank_rows(rows: list[dict], metric: str) -> list[dict]:
    ordered = sorted(rows, key=lambda row: score_key(row, metric))
    return [{**row, "rank": index + 1} for index, row in enumerate(ordered)]


def build_report(payload: dict, report_date: str) -> dict:
    day = next((item for item in payload.get("days", []) if item.get("date") == report_date), None)
    if day is None:
        raise ValueError(f"网页数据中找不到 {report_date} 日报。")

    personal = rank_rows(list(day.get("personal", [])), "score")
    matched = [row for row in personal if row.get("matched", True) and row.get("bigGroup") != "待确认班组"]

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
            result.append({**group, "headcount": headcount, "average": group["score"] / headcount if headcount else 0})
        return rank_rows(result, "average")

    return {
        "date": report_date,
        "personal": personal,
        "small": group_rows("smallGroup"),
        "big": group_rows("bigGroup"),
        "plus": sum(int(row.get("plus", 0)) for row in personal),
        "failure": sum(int(row.get("failure", 0)) for row in personal),
        "qc": sum(int(row.get("qc", 0)) for row in personal),
        "score": sum(int(row.get("score", 0)) for row in personal),
    }


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, radius: int = 18, outline: str | None = None) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2 if outline else 1)


def draw_centered(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], value: str, text_font: ImageFont.FreeTypeFont, fill: str) -> None:
    bounds = draw.textbbox((0, 0), value, font=text_font)
    x = box[0] + (box[2] - box[0] - (bounds[2] - bounds[0])) / 2
    y = box[1] + (box[3] - box[1] - (bounds[3] - bounds[1])) / 2 - bounds[1]
    draw.text((x, y), value, font=text_font, fill=fill)


def metric_text(value: float, kind: str) -> str:
    return str(int(value)) if kind == "personal" else f"{value:.2f}"


def draw_rank_section(draw: ImageDraw.ImageDraw, y: int, title: str, rows: list[dict], kind: str) -> None:
    left, right = 56, 1186
    draw.text((left, y), title, font=font(30, True), fill=COLORS["ink"])
    draw.text((right, y + 4), "按积分从高到低排序", font=font(18), fill=COLORS["muted"], anchor="ra")
    card_top = y + 52
    rounded(draw, (left, card_top, right, card_top + 324), COLORS["paper"], 18, COLORS["line"])
    middle = (left + right) // 2
    draw.line((middle, card_top + 18, middle, card_top + 306), fill=COLORS["line"], width=2)

    columns = [
        (left + 22, middle - 22, "TOP 3", rows[:3], COLORS["teal"], COLORS["teal_soft"]),
        (middle + 22, right - 22, "后三名", list(reversed(rows[-3:])), COLORS["red"], COLORS["red_soft"]),
    ]
    for x1, x2, label, selected, accent, soft in columns:
        draw.text((x1, card_top + 20), label, font=font(20, True), fill=accent)
        draw.line((x1, card_top + 56, x2, card_top + 56), fill=COLORS["line"], width=1)
        for index, row in enumerate(selected):
            row_y = card_top + 72 + index * 78
            rounded(draw, (x1, row_y, x1 + 48, row_y + 48), soft, 10)
            draw_centered(draw, (x1, row_y, x1 + 48, row_y + 48), str(row["rank"]), font(20, True), accent)
            context = (
                f'{row.get("bigGroup", "")}  {row.get("smallGroup", "")}'
                if kind == "personal"
                else f'{row.get("bigGroup", "")}  {row.get("headcount", 0)}人'
                if kind == "small"
                else f'{row.get("headcount", 0)}人'
            )
            draw.text((x1 + 64, row_y - 2), str(row["name"]), font=font(23, True), fill=COLORS["ink"])
            draw.text((x1 + 64, row_y + 30), context, font=font(16), fill=COLORS["muted"])
            value = row["score"] if kind == "personal" else row["average"]
            color = COLORS["teal"] if value > 0 else COLORS["red"] if value < 0 else COLORS["ink"]
            draw.text((x2, row_y + 10), metric_text(value, kind), font=font(27, True), fill=color, anchor="ra")


def generate(report: dict) -> Image.Image:
    image = Image.new("RGB", (1242, 2000), COLORS["canvas"])
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1242, 278), fill=COLORS["navy"])
    draw.rectangle((0, 270, 1242, 278), fill=COLORS["teal"])
    draw.text((56, 42), "中台报表平台", font=font(20), fill="#b9c8d8")
    draw.text((56, 80), "降档低签挽留日报", font=font(50, True), fill="#ffffff")
    year, month, day = report["date"].split("-")
    draw.text((1186, 96), f"{year}年{int(month)}月{int(day)}日", font=font(26, True), fill="#ffffff", anchor="ra")
    draw.text((1186, 140), "个人、小组及大组积分排名", font=font(19), fill="#b9c8d8", anchor="ra")

    kpis = [
        ("成功加分", report["plus"], COLORS["teal"]),
        ("失败扣分", report["failure"], COLORS["red"]),
        ("质检扣分", report["qc"], COLORS["amber"]),
        ("合计积分", report["score"], COLORS["navy2"]),
    ]
    card_width, gap, y = 270, 16, 208
    for index, (label, value, accent) in enumerate(kpis):
        x = 56 + index * (card_width + gap)
        rounded(draw, (x, y, x + card_width, y + 154), COLORS["paper"], 16)
        draw.rectangle((x, y, x + 6, y + 154), fill=accent)
        draw.text((x + 24, y + 20), label, font=font(19, True), fill=COLORS["muted"])
        value_color = COLORS["teal"] if label == "成功加分" else COLORS["red"] if value < 0 or "扣分" in label else COLORS["ink"]
        draw.text((x + 24, y + 55), str(value), font=font(45, True), fill=value_color)
        draw.text((x + 24, y + 119), "次数" if label != "合计积分" else "当日", font=font(15), fill=COLORS["muted"])

    draw.text((56, 396), "计分口径：成功 1次 +1分；失败 1次 −1分；质检不足 1次 −1分。", font=font(18), fill=COLORS["muted"])
    draw_rank_section(draw, 452, "个人积分排名", report["personal"], "personal")
    draw_rank_section(draw, 856, "小组人均积分排名", report["small"], "small")
    draw_rank_section(draw, 1260, "大组人均积分排名", report["big"], "big")

    draw.line((56, 1714, 1186, 1714), fill=COLORS["line"], width=2)
    draw.text((56, 1744), "说明", font=font(22, True), fill=COLORS["ink"])
    draw.text((56, 1786), "小组、大组按正式名单人数计算人均分；离职及待确认人员不计入组均分。", font=font(18), fill=COLORS["muted"])
    draw.text((56, 1822), "完整排名请查看网页报表。", font=font(18), fill=COLORS["muted"])
    rounded(draw, (56, 1874, 1186, 1940), COLORS["navy"], 14)
    draw.text((82, 1892), "降档低签挽留考核排名通报", font=font(20, True), fill="#ffffff")
    draw.text((1160, 1892), SITE_URL, font=font(16), fill="#c9d6e2", anchor="ra")
    return image


def main() -> int:
    parser = argparse.ArgumentParser(description="生成降档低签挽留PNG日报图片。")
    parser.add_argument("--date", help="日报日期，格式为 YYYY-MM-DD；默认读取刚导入的日期。")
    args = parser.parse_args()
    try:
        report_date = args.date or (LAST_DATE_FILE.read_text(encoding="utf-8").strip() if LAST_DATE_FILE.exists() else "")
        if not report_date:
            raise ValueError("没有找到刚导入的日报日期。")
        payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        report = build_report(payload, report_date)
        image = generate(report)
        LOCAL_OUTPUT.mkdir(parents=True, exist_ok=True)
        WEB_OUTPUT.mkdir(parents=True, exist_ok=True)
        local_path = LOCAL_OUTPUT / f"{report_date}_降档低签挽留日报.png"
        web_path = WEB_OUTPUT / f"{report_date}.png"
        image.save(local_path, format="PNG", optimize=True)
        image.save(web_path, format="PNG", optimize=True)
        print(f"已生成图片：{local_path}")
        return 0
    except Exception as exc:
        print(f"图片生成失败：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
