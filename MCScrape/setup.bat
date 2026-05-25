@echo off
setlocal enabledelayedexpansion

echo ==========================================
echo  Minecraft Toolchain One-Click Setup
echo ==========================================
echo.

:: ----------------------------
:: Ask for Minecraft username
:: ----------------------------
set /p MC_USERNAME=Enter your Minecraft username: 

if "%MC_USERNAME%"=="" (
    echo [!] Username cannot be empty
    pause
    exit /b 1
)

echo.
echo [+] Using username: %MC_USERNAME%

:: ----------------------------
:: Check Python
:: ----------------------------
python --version >nul 2>&1

if %errorlevel% neq 0 (
    echo [!] Python not found. Please install Python 3.10+ first.
    echo     https://www.python.org/downloads/
    pause
    exit /b 1
) else (
    echo [+] Python detected
)

:: ----------------------------
:: Check Node
:: ----------------------------
node --version >nul 2>&1

if %errorlevel% neq 0 (
    echo [!] Node.js not found. Installing via winget...

    winget install OpenJS.NodeJS.LTS

    echo.
    echo [+] Node install triggered.
    echo [+] Re-run this script after installation completes.

    pause
    exit /b 1
) else (
    echo [+] Node.js detected
)

:: ----------------------------
:: Generate authBootstrap.js
:: ----------------------------
echo.
echo ==========================================
echo Generating authBootstrap.js
echo ==========================================

(
echo const { Authflow } = require('prismarine-auth'^);
echo.
echo const user = "%MC_USERNAME%";
echo.
echo async function main^(^) {
echo   try {
echo     console.log^('[*] Starting Microsoft authentication...'^);
echo.
echo     const authflow = new Authflow^(
echo       user,
echo       './mc-cache'
echo     ^);
echo.
echo     const token = await authflow.getMinecraftJavaToken^(^);
echo.
echo     console.log^('[+] Authentication successful'^);
echo     console.log^('[+] Username:', token.profile.name^);
echo     console.log^('[+] UUID:', token.profile.id^);
echo     console.log^('[+] Cache saved to ./mc-cache'^);
echo.
echo     process.exit^(0^);
echo.
echo   } catch ^(err^) {
echo     console.log^('[!] Authentication failed'^);
echo     console.log^(err^);
echo.
echo     process.exit^(1^);
echo   }
echo }
echo.
echo main^(^);
) > authBootstrap.js

echo [+] authBootstrap.js generated

:: ----------------------------
:: Generate checkWhitelist.js
:: ----------------------------
echo.
echo ==========================================
echo Generating checkWhitelist.js
echo ==========================================

(
echo const mc = require^('minecraft-protocol'^);
echo.
echo const user = "%MC_USERNAME%";
echo.
echo const HOST = process.argv[2];
echo const PORT = parseInt^(process.argv[3] ^|^| "25565"^);
echo.
echo function checkServer^(host, port^) {
echo   return new Promise^((resolve^) =^> {
echo     let finished = false;
echo.
echo     const client = mc.createClient^({
echo       host,
echo       port,
echo       auth: 'microsoft',
echo       username: user
echo     }^);
echo.
echo     const timeout = setTimeout^(^(^) =^> {
echo       if ^(finished^) return;
echo.
echo       finished = true;
echo       client.end^(^);
echo.
echo       resolve^({ status: "timeout" }^);
echo     }, 8000^);
echo.
echo     client.on^('disconnect', ^(packet^) =^> {
echo       if ^(finished^) return;
echo.
echo       finished = true;
echo.
echo       clearTimeout^(timeout^);
echo       client.end^(^);
echo.
echo       const reason = JSON.stringify^(packet.reason ^|^| ''^).toLowerCase^(^);
echo.
echo       if ^(reason.includes^('whitelist'^)^) {
echo         resolve^({ status: "whitelist_blocked" }^);
echo       } else {
echo         resolve^({ status: "disconnected" }^);
echo       }
echo     }^);
echo.
echo     client.on^('end', ^(^) =^> {
echo       if ^(finished^) return;
echo.
echo       finished = true;
echo.
echo       clearTimeout^(timeout^);
echo.
echo       resolve^({ status: "ended" }^);
echo     }^);
echo.
echo     client.on^('error', ^(err^) =^> {
echo       if ^(finished^) return;
echo.
echo       finished = true;
echo.
echo       clearTimeout^(timeout^);
echo.
echo       resolve^({
echo         status: "error",
echo         error: err.message
echo       }^);
echo     }^);
echo   }^);
echo }
echo.
echo ^(async ^(^) =^> {
echo   const result = await checkServer^(HOST, PORT^);
echo.
echo   console.log^(JSON.stringify^(result^)^);
echo.
echo   process.exit^(0^);
echo }^)^(^);
) > checkWhitelist.js

echo [+] checkWhitelist.js generated

:: ----------------------------
:: Install Node dependencies
:: ----------------------------
echo.
echo ==========================================
echo Installing Node dependencies
echo ==========================================

if exist package.json (
    call npm install

    if %errorlevel% neq 0 (
        echo [!] npm install failed
        pause
        exit /b 1
    )

    echo [+] Node dependencies installed
) else (
    echo [!] No package.json found, skipping Node deps
)

:: ----------------------------
:: Install Python dependencies
:: ----------------------------
echo.
echo ==========================================
echo Installing Python dependencies
echo ==========================================

if exist requirements.txt (
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt

    if %errorlevel% neq 0 (
        echo [!] Python dependency install failed
        pause
        exit /b 1
    )

    echo [+] Python dependencies installed
) else (
    echo [!] No requirements.txt found, skipping Python deps
)

:: ----------------------------
:: Check auth cache
:: ----------------------------
echo.
echo ==========================================
echo Checking Minecraft auth cache
echo ==========================================

if not exist mc-cache\*.json (
    echo [!] No valid auth cache found
    echo [*] Launching authentication bootstrap...

    node authBootstrap.js

    if %errorlevel% neq 0 (
        echo [!] Authentication bootstrap failed
        pause
        exit /b 1
    )

    echo.
    echo [+] Authentication completed
) else (
    echo [+] Existing auth cache detected
)

:: ----------------------------
:: Finished
:: ----------------------------
echo.
echo ==========================================
echo Setup complete
echo ==========================================
echo Username: %MC_USERNAME%
echo You can now run your scripts.
echo.

pause
endlocal