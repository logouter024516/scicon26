# Missingfind GUI 실행 스크립트 (PowerShell)
#
# 이 스크립트는 Streamlit 웹 GUI를 실행합니다.
# 브라우저가 자동으로 열리고 http://localhost:8501 에서 확인할 수 있습니다.

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Missingfind GUI 대시보드 시작" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "브라우저가 자동으로 열립니다..." -ForegroundColor Green
Write-Host "종료하려면 Ctrl+C를 누르세요." -ForegroundColor Yellow
Write-Host ""

# Streamlit 실행
streamlit run src/app/streamlit_app.py

Write-Host ""
Write-Host "GUI가 종료되었습니다." -ForegroundColor Red
Read-Host "계속하려면 Enter를 누르세요"
