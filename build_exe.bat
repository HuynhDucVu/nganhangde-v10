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
echo   DONG GOI Nganhangde_vu-pro.exe (BAN TAC GIA - KHONG CAN KEY)
echo   Trinh Python su dung: %PYCMD%
echo ============================================================
%PYCMD% --version

echo.
echo [1/3] Cai dat thu vien tu requirements.txt...
%PYCMD% -m pip install --upgrade pip
%PYCMD% -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [LOI] Khong cai duoc thu vien. Hay cai Python 3.12 64-bit.
    pause
    exit /b 1
)

echo.
echo [2/3] Dong goi Nganhangde_vu-pro.exe bang PyInstaller...
%PYCMD% -m PyInstaller --noconfirm --clean NganHangDe.spec
if %errorlevel% neq 0 (
    echo [LOI] Dong goi PyInstaller that bai. Hay dung Python 3.12 64-bit.
    pause
    exit /b 1
)

:: Bo sung DLL neu thieu
for /f "delims=" %%D in ('%PYCMD% -c "import sys, pathlib; print(pathlib.Path(sys.base_prefix))"') do set PYBASE=%%D
if exist "%PYBASE%\python3*.dll" (
    for %%F in ("%PYBASE%\python3*.dll") do (
        if not exist "dist\Nganhangde_vu-pro\_internal\%%~nxF" copy /Y "%%F" "dist\Nganhangde_vu-pro\_internal\" >nul
    )
)
if exist "%PYBASE%\vcruntime140.dll" (
    if not exist "dist\Nganhangde_vu-pro\_internal\vcruntime140.dll" copy /Y "%PYBASE%\vcruntime140.dll" "dist\Nganhangde_vu-pro\_internal\" >nul
)
if exist "HUONG_DAN_SU_DUNG.txt" copy /Y "HUONG_DAN_SU_DUNG.txt" "dist\Nganhangde_vu-pro\HUONG_DAN_SU_DUNG.txt" >nul

echo.
echo [3/3] HOAN TAT BAN PRO!
echo   Mo tep chay: dist\Nganhangde_vu-pro\Nganhangde_vu-pro.exe
echo   (Muon dong goi ban TINH PHI gui khach hang, chay: build_exe_ban_tinh_phi.bat)
pause
