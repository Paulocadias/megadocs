@echo off
setlocal EnableDelayedExpansion

REM Read .env file
if not exist .env (
    echo Error: .env file not found!
    pause
    exit /b 1
)

REM Parse .env for GITHUB_TOKEN
for /f "usebackq tokens=1* delims==" %%A in (".env") do (
    if "%%A"=="GITHUB_TOKEN" set GITHUB_TOKEN=%%B
)

if "%GITHUB_TOKEN%"=="" (
    echo Error: GITHUB_TOKEN not found in .env file.
    pause
    exit /b 1
)

REM Ensure Git Repo exists - Self Healing
if not exist .git (
    echo [Fixing] Initializing Git repository...
    git init
    git add .
    git commit -m "Final Release: Security, Docs, and Deployment Scripts"
    git branch -M main
) else (
    echo [Check] Git repository found.
    git add .
    git commit -m "Update before push" >nul 2>&1
)

REM Configure Remote (Force update)
echo [Configuring] Setting remote origin...
git remote remove origin >nul 2>&1
git remote add origin https://github.com/Paulocadias/DOCSsite.git

echo [Pushing] Uploading code to GitHub...
git push https://Paulocadias:%GITHUB_TOKEN%@github.com/Paulocadias/DOCSsite.git main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo SUCCESS! Your code is now on GitHub.
    echo ========================================
) else (
    echo.
    echo ========================================
    echo FAILED. Please check the error above.
    echo ========================================
)

pause
endlocal
