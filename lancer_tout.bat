@echo off
chcp 65001 > nul
echo.
echo ================================================
echo   VICTOR V2 — LANCEMENT AUTOMATIQUE
echo ================================================
echo.

REM Aller dans le dossier du projet
cd /d C:\victor_v2

REM Utiliser Python 3.10
set PYTHON="C:\Users\mbath\AppData\Local\Programs\Python\Python310\python.exe"

echo [%time%] Installation de psutil si necessaire...
%PYTHON% -m pip install psutil -q

echo.
echo [%time%] Lancement du script automatique...
echo.

%PYTHON% lancer_tout.py

echo.
echo ================================================
echo   TERMINE - Appuie sur une touche pour fermer
echo ================================================
pause