@echo off
chcp 65001 >nul
setlocal
rem ============================================================
rem  PHAT HANH BAN MOI - chay tu thu muc clone cua repo nganhangde-v10
rem  Cach dung:
rem    phat_hanh.bat "D:\duong_dan\ban_moi" 8.2.0 "Mo ta thay doi"
rem    phat_hanh.bat "D:\duong_dan\ban_moi" 8.2.0 "Mo ta thay doi" thu
rem      (them chu "thu" de chi kiem tra, khong day len GitHub)
rem ============================================================

if "%~3"=="" (
    echo [CACH DUNG] phat_hanh.bat "thu_muc_hoac_zip_ban_moi" PHIEN_BAN "mo ta thay doi" [thu]
    echo   Vi du: phat_hanh.bat "D:\Nganhangde-v10\Nganhangde_vu-pro_v8.2" 8.2.0 "Them tinh nang X"
    pause
    exit /b 1
)

cd /d "%~dp0"

where git >nul 2>&1 || (echo [LOI] Chua cai Git. & pause & exit /b 1)
where python >nul 2>&1 || (echo [LOI] Chua cai Python. & pause & exit /b 1)

echo [1/3] Lay code moi nhat tu GitHub...
git pull --ff-only origin main
if errorlevel 1 (
    echo [LOI] Khong lay duoc code moi. Kiem tra mang hoac thu muc co thay doi chua commit.
    pause & exit /b 1
)

set "DRY="
if /i "%~4"=="thu" set "DRY=--dry-run"

echo [2/3] Kiem tra, tang phien ban, commit va tao tag %2 ...
python tools\publish_update.py "%~1" --version %2 -m "%~3" %DRY%
if errorlevel 1 (
    echo.
    echo [DUNG] Phat hanh that bai. Khong co gi duoc day len GitHub.
    pause & exit /b 1
)

if /i "%~4"=="thu" (
    echo.
    echo [XONG] Da kiem tra thanh cong ban %2 (chua day len GitHub).
    pause & exit /b 0
)

echo [3/3] Da day len GitHub.
echo   GitHub se tu build va dang Release v%2 trong khoang 5-10 phut.
echo   Theo doi tien trinh tai: https://github.com/HuynhDucVu/nganhangde-v10/actions
echo   Khach dang dung ban cu se thay thong bao cap nhat khi mo phan mem.
pause
exit /b 0
