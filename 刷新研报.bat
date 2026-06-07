@echo off
chcp 65001 >nul
echo ========================================
echo   期货研报数据刷新工具
echo ========================================
echo.
echo 正在从东方财富/新浪财经抓取最新研报...
echo.

cd /d "%~dp0"
python scripts\fetch_morning_reports.py

echo.
echo ========================================
echo   刷新完成！数据已保存到 data\reports.json
echo   刷新面板页面即可看到最新研报
echo ========================================
echo.
pause
