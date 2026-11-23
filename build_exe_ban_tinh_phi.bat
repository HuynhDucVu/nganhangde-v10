@echo off
chcp 65001 >nul
set PYCMD=python
py -3.12 --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYCMD=py -3.12
) else (
    py -3.11 --version >nul 2>&1
    if %errorlevel% equ 0 set PYCMD=py -3.11
)

echo ============================================================
echo   DONG GOI BAN TINH PHI GUI KHACH HANG (BAT BUOC KEY MA MAY)
echo ============================================================

if "%NGANHANGDE_LICENSE_SECRET%"=="" (
    echo [LOI] Chua dat bien moi truong NGANHANGDE_LICENSE_SECRET ^(khoa ban quyen^).
    echo        Vi du: set NGANHANGDE_LICENSE_SECRET=gia_tri_khoa_cua_ban
    pause
    exit /b 1
)

:: Nhung khoa ban quyen tu bien moi truong (se duoc khoi phuc lai sau khi build)
%PYCMD% tools\set_license_secret.py inject
if %errorlevel% neq 0 (
    pause
    exit /b 1
)

:: Tam thoi chuyen AUTHOR_PRO_MODE = False va doi ten exe thanh Nganhangde_vu
%PYCMD% -c "from pathlib import Path; p=Path('nganhangde/core/licensing.py'); p.write_text(p.read_text(encoding='utf-8').replace('AUTHOR_PRO_MODE = True','AUTHOR_PRO_MODE = False',1), encoding='utf-8')"
%PYCMD% -c "from pathlib import Path; p=Path('NganHangDe.spec'); p.write_text(p.read_text(encoding='utf-8').replace('name=\"Nganhangde_vu-pro\"','name=\"Nganhangde_vu\"'), encoding='utf-8')"

%PYCMD% -m PyInstaller --noconfirm --clean NganHangDe.spec
set BUILD_ERR=%errorlevel%

:: Khoi phuc placeholder khoa ban quyen (khong de khoa trong thu muc lam viec)
%PYCMD% tools\set_license_secret.py restore

:: Tu dong khoi phuc lai trang thai ban Pro cho tac gia
%PYCMD% -c "from pathlib import Path; p=Path('nganhangde/core/licensing.py'); p.write_text(p.read_text(encoding='utf-8').replace('AUTHOR_PRO_MODE = False','AUTHOR_PRO_MODE = True',1), encoding='utf-8')"
%PYCMD% -c "from pathlib import Path; p=Path('NganHangDe.spec'); p.write_text(p.read_text(encoding='utf-8').replace('name=\"Nganhangde_vu\"','name=\"Nganhangde_vu-pro\"'), encoding='utf-8')"

if %BUILD_ERR% neq 0 (
    echo [LOI] Dong goi ban tinh phi that bai!
    pause
    exit /b %BUILD_ERR%
)

for /f "delims=" %%D in ('%PYCMD% -c "import sys, pathlib; print(pathlib.Path(sys.base_prefix))"') do set PYBASE=%%D
if exist "%PYBASE%\python3*.dll" (
    for %%F in ("%PYBASE%\python3*.dll") do (
        if not exist "dist\Nganhangde_vu\_internal\%%~nxF" copy /Y "%%F" "dist\Nganhangde_vu\_internal\" >nul
    )
)
if exist "HUONG_DAN_SU_DUNG.txt" copy /Y "HUONG_DAN_SU_DUNG.txt" "dist\Nganhangde_vu\HUONG_DAN_SU_DUNG.txt" >nul

powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path 'Nganhangde_vu_v7.9_BanTinhPhi.zip') { Remove-Item 'Nganhangde_vu_v7.9_BanTinhPhi.zip' -Force }; Compress-Archive -Path 'dist\Nganhangde_vu\*' -DestinationPath 'Nganhangde_vu_v7.9_BanTinhPhi.zip' -Force"

echo.
echo ============================================================
echo   [HOAN TAT] Tep gui khach hang: Nganhangde_vu_v7.9_BanTinhPhi.zip
echo   (Ma nguon cua ban da duoc tu dong tra lai che do Pro khong can Key!)
echo ============================================================
pause
