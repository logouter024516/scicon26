@echo off
REM Missingfind GUI 실행 스크립트
REM
REM 이 스크립트는 Streamlit 웹 GUI를 실행합니다.
REM 브라우저가 자동으로 열리고 http://localhost:8501 에서 확인할 수 있습니다.

echo.
echo ========================================
echo    Missingfind GUI 대시보드 시작
echo ========================================
echo.
echo 브라우저가 자동으로 열립니다...
echo 종료하려면 Ctrl+C를 누르세요.
echo.

streamlit run src/app/streamlit_app.py

echo.
echo GUI가 종료되었습니다.
pause
