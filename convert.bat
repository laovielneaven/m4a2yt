@echo off
rem ============================================================
rem  m4a2yt - drag & drop helper
rem  Taruh file .m4a (atau folder) ke ikon convert.bat ini,
rem  hasil muncul di folder output\
rem ============================================================
python "%~dp0m4a2yt.py" %*
echo.
pause
