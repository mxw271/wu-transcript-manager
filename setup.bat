@echo off
chcp 65001 >nul
SETLOCAL ENABLEDELAYEDEXPANSION

echo Setting Up WU Transcript Manager...

:: --- Script Directory Setup --- 
set "SCRIPT_DIR=%~dp0"
cd /d %SCRIPT_DIR%
echo Running in: %CD%

:: --- Check if Running as Administrator ---
fsutil dirty query %SystemDrive% >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo This script requires Administrator privileges. Restarting with Admin rights...
    echo Press Yes when prompted.
    runas /savecred /user:Administrator "%~s0"
    exit /b
)

:: --- Dependency Checks ---
echo Checking dependencies...

:: --- Python 3.9+ ---
echo Checking for Python 3.9+...
set "PYTHON_PATH="
set "PYTHON_VERSION="
for /f "tokens=*" %%p in ('where python 2^>nul') do (
    for /f "tokens=2 delims= " %%v in ('"%%p" --version 2^>nul') do (
        set "PYTHON_VERSION=%%v"
        for /f "tokens=1,2 delims=." %%a in ("%%v") do (
            if %%a EQU 3 (
                if %%b GEQ 9 (
                    set "PYTHON_PATH=%%p"
                    goto :PYTHON_FOUND
                )
            )
        )
    )
)
:PYTHON_FOUND
if defined PYTHON_PATH (
    echo Python 3.9+ detected: %PYTHON_PATH%. Version: %PYTHON_VERSION%
) else (
    echo Python 3.9+ missing or outdated. Installing...

    :: Fetch the latest Python version number using endoflife.date API
    for /f "delims=" %%a in ('curl -s https://endoflife.date/api/python.json') do ( 
        for %%b in (%%a) do (
            if not defined PYTHON_VERSION (
                echo %%b | findstr /B /C:"\"latest\":" >nul && (
                    for /f "tokens=2 delims=:" %%c in ("%%b") do (
                        set "PYTHON_VERSION=%%c"
                        set "PYTHON_VERSION=!PYTHON_VERSION:~1,-1!"
                    )
                )
            )
        )
    )
    echo Latest Python version: !PYTHON_VERSION!
    
    set "PYTHON_URL=https://www.python.org/ftp/python/!PYTHON_VERSION!/python-!PYTHON_VERSION!-amd64.exe"
    curl -O !PYTHON_URL!
    start /wait python-!PYTHON_VERSION!-amd64.exe /quiet InstallAllUsers=1 PrependPath=1

    :: Set Python path
    set "PYTHON_PATH=C:\Program Files\Python!PYTHON_VERSION:~0,1!!PYTHON_VERSION:~2,2!\python.exe"
    set "PYTHON_DIR=C:\Program Files\Python!PYTHON_VERSION:~0,1!!PYTHON_VERSION:~2,2!"
    echo PYTHON_PATH: "!PYTHON_PATH!"
    echo PYTHON_DIR: "!PYTHON_DIR!"
    setx PATH "!PATH!;!PYTHON_DIR!;!PYTHON_DIR!\Scripts" /M

    :: Wait for installation to complete and delete installation file.
    timeout /t 10 >nul
    del /f /q python-!PYTHON_VERSION!-amd64.exe
)

:: --- virtualenv ---
"!PYTHON_PATH!" -m virtualenv --version >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo virtualenv missing. Installing...
    "!PYTHON_PATH!" -m pip install --user virtualenv
) else (
    echo virtualenv already exists.
)

:: --- Node.js (v20+) ---
echo Checking for Node.js v20+...
set "NODE_PATH="
set "NODE_VERSION="
for /f "delims=" %%n in ('where node 2^>nul') do (
    if not defined NODE_PATH set "NODE_PATH=%%n"
)
if defined NODE_PATH (
    for /f "tokens=*" %%v in ('"%NODE_PATH%" -v 2^>nul') do (
        echo Node.js Version Output: %%v
        set "NODE_VERSION=%%v"
        for /f "tokens=1,2,3 delims=." %%a in ("%%v") do (
            if %%a GEQ 20 (
                if %%b GEQ 0 (
                    set "NODE_PATH=%%p"
                    goto :NODE_FOUND
                )
            )
        )
    )
)
:NODE_FOUND
if defined NODE_PATH (
    echo Node.js v20+ detected: %NODE_PATH%. Version: %NODE_VERSION%
) else (
    echo Node.js v20+ missing or outdated. Installing...

    for /f "tokens=*" %%a in ('curl -s https://nodejs.org/dist/latest/ ^| findstr /r /c:"node-v.*-x64.msi"') do ( 
        for /f "tokens=2 delims=-" %%b in ("%%a") do ( 
            for /f "tokens=1 delims=." %%c in ("%%b") do ( 
                set "NODE_VERSION=%%b" 
                set "NODE_MSI=node-%%b-x64.msi" 
                goto :MSI_FOUND 
            ) 
        ) 
    ) 
    :MSI_FOUND 
    set "NODE_URL=https://nodejs.org/dist/latest/%NODE_MSI%"
    curl -O %NODE_URL%
    start /wait msiexec /i %NODE_MSI% /quiet
    
    set "NODE_PATH=C:\Program Files\nodejs\node.exe"
    echo NODE_PATH: "!NODE_PATH!"
    echo NODE_PATH: "%NODE_PATH%"
    setx PATH "%PATH%;C:\Program Files\nodejs;" /M

    :: Wait for installation to complete and delete installation file.
    timeout /t 10 >nul
    del /f /q %NODE_MSI%
)

:: --- Tesseract ---
echo Checking for Tesseract 5.3.0+...
set "TESS_PATH="
set "TESS_VERSION="
for /f "delims=" %%t in ('where tesseract 2^>nul') do (
    if not defined TESS_PATH set "TESS_PATH=%%~t"
)
if defined TESS_PATH (
    for /f "tokens=2" %%v in ('cmd /c ""%TESS_PATH%" --version 2^>nul" ^| findstr /R "^tesseract [0-9]\.[0-9]\.[0-9]"') do (
        if not defined TESS_VERSION (
            echo Tesseract Version Output: %%v
            set "TESS_VERSION=%%v"
            for /f "tokens=1,2 delims=." %%a in ("%%v") do (
                if %%a EQU 5 (
                    if %%b GEQ 3 (
                        goto :TESS_FOUND
                    )
                )
            )
        )
    )
)
:TESS_FOUND
if defined TESS_PATH (
    echo Tesseract 5.3+ detected: "%TESS_PATH%". Version: %TESS_VERSION%
) else (
    echo Tesseract 5.3+ missing. Installing...

    for /f "tokens=*" %%a in ('curl -s https://api.github.com/repos/UB-Mannheim/tesseract/releases/latest ^| findstr /i "browser_download_url" ^| findstr /i ".exe"') do (
        echo %%a
        for /f "tokens=3 delims=:" %%b in ("%%a") do (
            set "TESS_URL=https:%%b"
            set "TESS_URL=!TESS_URL:~0,-1!"
            goto :TESS_URL_FOUND
        )
    )
    :TESS_URL_FOUND
    echo %TESS_URL%
    echo !TESS_URL!
    curl -L -o tesseract-installer.exe !TESS_URL!
    start /wait tesseract-installer.exe /SILENT
     
    set "TESS_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe"
    echo %TESS_PATH%
    echo !TESS_PATH!
    setx PATH "%PATH%;C:\Program Files\Tesseract-OCR;" /M
  
    :: Wait for installation to complete and delete installation file.
    timeout /t 10 >nul
    del /f /q tesseract-installer.exe
)

:: Set TESSDATA_PREFIX
setx TESSDATA_PREFIX "C:\Program Files\Tesseract-OCR\tessdata"

:: --- Backend Setup ---
echo Setting up the backend...
if not exist "%SCRIPT_DIR%\backend" mkdir "%SCRIPT_DIR%\backend"
cd "%SCRIPT_DIR%\backend"

:: Create virtual environment
if not exist venv (
    echo Creating Python virtual environment...
    "%PYTHON_PATH%" -m venv venv
)

:: Activate virtual environment
call venv\Scripts\activate
echo Virtual environment activated.

:: Install dependencies
echo Installing backend dependencies...
if exist "requirements.txt" (
    "%PYTHON_PATH%" -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    echo No requirements.txt found. Skipping dependency installation.
)


:: ---- Database Setup ----
echo Setting up database...

if not exist "%SCRIPT_DIR%\database" (
    echo Database folder missing. Creating...
    mkdir "%SCRIPT_DIR%\database"
) else (
    echo Database folder exists.
)

set "DB_PATH=%SCRIPT_DIR%\database\database.db"
set "OFFICIAL_DB=%SCRIPT_DIR%\database\official_database.db"
set "BACKUP_PATH=%SCRIPT_DIR%\database\database_backup_%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%.db"

:: Handling different database scenarios
if not exist "%DB_PATH%" if not exist "%OFFICIAL_DB%" (
    echo No database found. Creating a new one...
    python -c "from db_create_tables import initialize_database; initialize_database(r'%DB_PATH%')"
    echo New database initialized at %DB_PATH%
    goto :end
) 

if exist "%DB_PATH%" if not exist "%OFFICIAL_DB%" (
    echo database.db exists. No migration needed.
    goto :end
) 

if not exist "%DB_PATH%" if exist "%OFFICIAL_DB%" (
    echo No database.db found, but official_database.db exists.
    echo Migrating official_database.db and using it as database.db...
    copy "%OFFICIAL_DB%" "%DB_PATH%"
    call :verify_database
    goto :end
) 

if exist "%DB_PATH%" if exist "%OFFICIAL_DB%" (
    echo Both database.db and official_database.db exist.
    echo Creating a backup before migration: %BACKUP_PATH%
    copy "%DB_PATH%" "%BACKUP_PATH%"

    echo Migrating official_database.db and using it as database.db...
    copy "%OFFICIAL_DB%" "%DB_PATH%"
    call :verify_database
    goto :end
)

:: Subroutine to verify schema and check database content
:verify_database
echo Verifying database schema...
python -c "from db_create_tables import initialize_database; initialize_database(r'%DB_PATH%')"

echo Checking database content...
python -c "from db_service import check_database_content; check_database_content(r'%DB_PATH%')"
exit /b

:end
echo DATABASE_FILE set to: %DB_PATH%
cd ..

:: --- Frontend Setup (Pure React) ---
echo Setting up the frontend...

:: Create frontend directory if it doesn't exist
if not exist "%SCRIPT_DIR%frontend" (
    echo Creating React app...
    call "%NODE_PATH%" exec npx create-react-app frontend || echo Error running npx && pause
)
cd frontend

:: Find npm path
set "NPM_PATH="
for /f "delims=" %%n in ('where npm 2^>nul') do (
    if not defined NPM_PATH set "NPM_PATH=%%n"
)

:: Install frontend dependencies
echo Installing frontend dependencies...
call "%NPM_PATH%" install --legacy-peer-deps

cd ..

:: --- Completion Messages ---
:: Deactivate virtual environment
call backend\venv\Scripts\deactivate >nul 2>&1

echo Setup complete! Run './start.sh' to start the servers.
echo You may now close this window.
cmd /k
