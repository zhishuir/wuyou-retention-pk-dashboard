from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "营销PK赛模板.xlsx"

HEADER_FILL = PatternFill("solid", fgColor="112B46")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)


def style_header(*cells) -> None:
    for cell in cells:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")


def main() -> int:
    wb = Workbook()

    ws1 = wb.active
    ws1.title = "项目分值"
    ws1.append(["项目名称", "分值"])
    ws1["A1"].comment = Comment("填写加分项目名称，例如：首投成功。", "模板说明")
    ws1["B1"].comment = Comment("该项目每出现一次加多少分，例如：5。必须是大于0的数字。", "模板说明")
    ws1.column_dimensions["A"].width = 24
    ws1.column_dimensions["B"].width = 12
    style_header(ws1["A1"], ws1["B1"])

    ws2 = wb.create_sheet("加分记录")
    ws2.append(["日期", "姓名", "项目"])
    ws2["A1"].comment = Comment("可选，格式如 2026-09-18，仅用于记录，不影响计分。", "模板说明")
    ws2["B1"].comment = Comment("必填，员工姓名，须与挽留考核名单中的姓名一致。", "模板说明")
    ws2["C1"].comment = Comment("必填，项目名称，须与「项目分值」表中的项目名完全一致。", "模板说明")
    ws2.column_dimensions["A"].width = 14
    ws2.column_dimensions["B"].width = 14
    ws2.column_dimensions["C"].width = 24
    style_header(ws2["A1"], ws2["B1"], ws2["C1"])

    ws3 = wb.create_sheet("填写说明")
    for row in (
        "营销PK赛模板填写说明",
        "",
        "1. 在「项目分值」表维护加分项目和分值，一行一个项目。",
        "2. 在「加分记录」表逐行记录每次加分：姓名 + 项目（日期可选）。",
        "3. 每出现一次，就按该项目分值加一次分；同一人可以出现多次。",
        "4. 姓名必须与挽留考核名单一致，程序会自动匹配大组和小组。",
        "5. 排名口径：个人按累计积分；小组、大组按人均积分（累计积分 ÷ 参赛人数）。",
        "6. 填好后把文件放入「待发布PK」文件夹，双击「更新并发布.bat」即可。",
        "7. 只加分、不扣分；未匹配到名单的姓名会归入「待确认班组」，不计入班组人均。",
    ):
        ws3.append([row])
    ws3.column_dimensions["A"].width = 72

    wb.save(OUTPUT)
    print(f"已生成模板：{OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
