@echo off
chcp 65001 >nul
set PYCMD=python
py -3.12 --version >nul 2>&1
if %errorlevel% equ 0 set PYCMD=py -3.12
%PYCMD% admin_keygen_gui.py
if %errorlevel% neq 0 pause
