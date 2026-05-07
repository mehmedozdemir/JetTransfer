@echo off
echo.
echo ========================================================
echo         JetTransfer Windows 11 Build Script
echo ========================================================
echo.

echo [1/3] Checking PyInstaller...
IF NOT EXIST "venv\Scripts\pyinstaller.exe" (
    echo PyInstaller not found. Installing into venv...
    .\venv\Scripts\pip.exe install pyinstaller
) ELSE (
    echo PyInstaller is ready.
)

echo.
echo [2/3] Building the standalone application (EXE)...
echo This may take a few minutes. Please wait...
.\venv\Scripts\pyinstaller.exe --noconsole --noconfirm --name "JetTransfer" --windowed main.py
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller build failed!
    pause
    exit /b %errorlevel%
)
echo PyInstaller build successful! Output is in the "dist\JetTransfer" folder.

echo.
echo [3/3] Building the Windows Installer Setup using Inno Setup...
:: Check common paths for Inno Setup compiler
SET ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

IF EXIST %ISCC% (
    echo Inno Setup Compiler found: %ISCC%
    %ISCC% "JetTransfer_Installer.iss"
    if %errorlevel% neq 0 (
        echo [ERROR] Inno Setup build failed!
        pause
        exit /b %errorlevel%
    )
    echo Installer build successful! Check the "Output" folder for the setup file.
) ELSE (
    echo [WARNING] Inno Setup Compiler (ISCC.exe) was not found at %ISCC%
    echo Please install "Inno Setup 6" from https://jrsoftware.org/isinfo.php to generate the Setup.exe file.
    echo After installing, you can either re-run this script or right-click 'JetTransfer_Installer.iss' and select 'Compile'.
)

echo.
echo Build process finished successfully.
pause
