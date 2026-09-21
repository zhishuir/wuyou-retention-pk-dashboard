@echo off
chcp 936 >nul
setlocal enabledelayedexpansion
title 降档低签挽留 - 日报与营销PK更新
cd /d "%~dp0"

echo ==================================================
echo   降档低签挽留 - 日报更新与发布
echo ==================================================
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo [失败] 未检测到 Python 启动器 py。
  echo 请先安装 Python 3，并勾选“Add Python to PATH”。
  goto :failed
)

where git >nul 2>nul
if errorlevel 1 (
  echo [失败] 未检测到 Git。
  echo 请先安装 Git for Windows。
  goto :failed
)

if not exist ".git" (
  echo [失败] 当前目录还没有完成 GitHub 初始化。
  echo 请先完成首次部署，再使用本脚本日更。
  goto :failed
)

if not exist "待发布日报" mkdir "待发布日报"
for %%F in ("待发布日报\*.xlsx" "待发布日报\*.xlsm") do if exist "%%~fF" set HAS_REPORT=1

if not exist "待发布PK" mkdir "待发布PK"
for %%F in ("待发布PK\*.xlsx" "待发布PK\*.xlsm") do if exist "%%~fF" set HAS_PK=1

if not defined HAS_REPORT if not defined HAS_PK (
  echo [提示] “待发布日报”和“待发布PK”文件夹中都没有 Excel 文件。
  echo 日报请放入“待发布日报”（文件名须含日期，如 2026-09-14三列日报.xlsx）；
  echo 营销PK赛请把填写好的模板放入“待发布PK”。
  start "" explorer.exe "%CD%\待发布日报"
  start "" explorer.exe "%CD%\待发布PK"
  goto :failed
)

if defined HAS_REPORT (
  echo [1/4] 正在读取最新日报并更新网页数据...
  py -3 tools\update_from_workbook.py
  if errorlevel 1 goto :failed

  echo [2/4] 正在生成微信日报图片...
  py -3 tools\generate_daily_image.py
  if errorlevel 1 goto :failed

  set "DOW="
  for /f "delims=" %%d in ('powershell -NoProfile -Command "[int](Get-Date).DayOfWeek"') do set "DOW=%%d"
  if "!DOW!"=="0" (
    echo [2b/4] 今天是周日，正在生成本周周报...
    py -3 tools\generate_weekly_image.py
    if errorlevel 1 goto :failed
  )
)

if defined HAS_PK (
  echo [PK] 正在读取营销PK赛模板并更新排名...
  py -3 tools\update_pk_from_workbook.py
  if errorlevel 1 goto :failed
  if not exist "待发布PK\已发布" mkdir "待发布PK\已发布"
  move /y "待发布PK\*.xlsx" "待发布PK\已发布\" >nul 2>nul
  move /y "待发布PK\*.xlsm" "待发布PK\已发布\" >nul 2>nul
)

echo [3/4] 正在生成版本记录...
git add dist\data\report-data.json dist\images\reports dist\data\pk-data.json
git diff --cached --quiet
if not errorlevel 1 goto :nothing

git commit -m "data: update ranking"
if errorlevel 1 goto :failed

echo [4/4] 正在发布到 GitHub...
git push
if errorlevel 1 goto :failed

echo.
echo 数据已发布，网页将在数分钟内自动更新。
echo 网址：https://zhishuir.github.io/wuyou-retention-pk-dashboard/
echo 日报图片已保存在“通报图片”文件夹，可直接发送到微信群。
start "" explorer.exe "%CD%\通报图片"
pause
goto :end

:nothing
echo.
echo 没有新的数据需要发布。
echo 图片已重新生成，可在“通报图片”文件夹中查看。
start "" explorer.exe "%CD%\通报图片"
pause
goto :end

:failed
echo.
echo 操作未完成，请检查上方提示后重试。
pause

:end
endlocal
