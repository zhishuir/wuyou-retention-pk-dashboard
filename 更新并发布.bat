@echo off
chcp 936 >nul
setlocal
title 降档低签挽留 - 日报更新
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
if not defined HAS_REPORT (
  echo [提示] “待发布日报”文件夹中没有 Excel 日报。
  echo 请把日报 .xlsx 文件放入该文件夹后重新运行。
  echo 文件名必须包含日期，例如：2026-09-14三列日报.xlsx
  start "" explorer.exe "%CD%\待发布日报"
  goto :failed
)

echo [1/4] 正在读取最新日报并更新网页数据...
py -3 tools\update_from_workbook.py
if errorlevel 1 goto :failed

echo [2/4] 正在生成微信日报图片...
py -3 tools\generate_daily_image.py
if errorlevel 1 goto :failed

echo [3/4] 正在生成版本记录...
git add dist\data\report-data.json dist\images\reports
git diff --cached --quiet
if not errorlevel 1 goto :nothing

git commit -m "data: update daily ranking"
if errorlevel 1 goto :failed

echo [4/4] 正在发布到 GitHub...
git push
if errorlevel 1 goto :failed

echo.
echo 日报已发布，网页将在数分钟内自动更新。
echo 网址：https://zhishuir.github.io/wuyou-retention-pk-dashboard/
echo 图片已保存在“通报图片”文件夹，可直接发送到微信群。
start "" explorer.exe "%CD%\通报图片"
pause
goto :end

:nothing
echo.
echo 没有新的日报数据需要发布。
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
