@echo off
cls
echo.
echo   ╔══════════════════════════════════════╗
echo   ║       🚀 CRYPTO DASHBOARD PRO       ║
echo   ╚══════════════════════════════════════╝
echo.

:: Verificar se app.py existe
if not exist "app.py" (
    echo ❌ Arquivo app.py nao encontrado!
    echo    Certifique-se de ter o arquivo app.py na pasta atual.
    pause
    exit /b 1
)

:: Instalar dependencias rapidamente
echo [1/2] Instalando dependencias necessarias...
pip install Flask Flask-CORS requests
echo.

:: Verificar instalacao
python -c "import flask, flask_cors, requests; print('✅ Dependencias instaladas com sucesso!')" 2>nul
if %errorlevel% neq 0 (
    echo ❌ Erro na instalacao das dependencias!
    echo    Tente executar manualmente: pip install Flask Flask-CORS requests
    pause
    exit /b 1
)

:: Executar dashboard
echo [2/2] Iniciando dashboard...
echo.
echo ✅ Dashboard iniciando em: http://localhost:5000
echo ❌ Para parar: Ctrl+C
echo.
echo ==========================================
echo.

python app.py

echo.
echo Dashboard encerrado.
pause