@echo off
chcp 65001 >nul
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo [LOI] May chua cai Git. Tai tai: https://git-scm.com/download/win
    pause
    exit /b 1
)

set "REPO_URL=%~1"
if "%REPO_URL%"=="" set /p "REPO_URL=Nhap link GitHub repo [Enter = https://github.com/HuynhDucVu/nganhangde-v10.git]: "
if "%REPO_URL%"=="" set "REPO_URL=https://github.com/HuynhDucVu/nganhangde-v10.git"

set "TAG_VER="
set /p "TAG_VER=Nhap tag phat hanh [VD: v7.9.0, de trong neu chi luu code]: "

git config --global user.name "HuynhDucVu" >nul 2>&1
git config --global user.email "HuynhDucVu@users.noreply.github.com" >nul 2>&1

if not exist ".git" (
    git init
    git branch -M main
)
git add .
git commit -m "Cap nhat Nganhangde_vu-pro v7.9.0"
git remote remove origin >nul 2>&1
git remote add origin "%REPO_URL%"
git push -u origin main

if "%TAG_VER%"=="" goto :done_only_code
git tag -f "%TAG_VER%"
git push -f origin "%TAG_VER%"
echo.
echo [XONG] Da day tag %TAG_VER%! GitHub Actions dang tu dong build ban tinh phi
echo        va dang len Releases de dong nghiep tu cap nhat.
goto :end_script

:done_only_code
echo.
echo [XONG] Da day ma nguon len GitHub thanh cong!

:end_script
pause
