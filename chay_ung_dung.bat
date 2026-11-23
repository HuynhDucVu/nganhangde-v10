@echo off
chcp 65001 >nul
set PYCMD=python
py -3.12 --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYCMD=py -3.12
) else (
    py -3.11 --version >nul 2>&1
    if %errorlevel% equ 0 (
        set PYCMD=py -3.11
    ) else (
        py -3.13 --version >nul 2>&1
        if %errorlevel% equ 0 set PYCMD=py -3.13
    )
)

echo ============================================================
echo   CHAY TRUC TIEP Nganhangde_vu-pro v7.9.0 (BAN TAC GIA)
echo   Trinh Python: %PYCMD%
echo ============================================================
echo [1/2] Kiem tra thu vien can thiet...
%PYCMD% -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [LOI] Hay cai Python 3.12 64-bit tai python.org (tich Add to PATH).
    pause
    exit /b 1
)
echo [2/2] Dang mo Nganhangde_vu-pro (khong can Key)...
%PYCMD% run_gui.py
if %errorlevel% neq 0 pause
