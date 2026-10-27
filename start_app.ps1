param(
    [switch]$Restart,
    [switch]$Stop,
    [switch]$Status
)

$ErrorActionPreference = 'Stop'
if (([int]$Restart.IsPresent + [int]$Stop.IsPresent + [int]$Status.IsPresent) -gt 1) {
    throw 'Use only one of -Restart, -Stop, or -Status.'
}
$taskRoot = $PSScriptRoot
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
$taskLauncher = Join-Path $taskRoot 'local_server.py'
$taskStatusUrl = 'http://127.0.0.1:5000/_local/status'

if (-not (Test-Path -LiteralPath $taskPython -PathType Leaf)) {
    throw 'Create the project .venv and install requirements.txt first. See README.md.'
}

function Get-AppStatus {
    try {
        $result = Invoke-RestMethod -Uri $taskStatusUrl -TimeoutSec 2
        if ($result.application -eq 'cloud-transaction-app' -and $result.project_root -eq $taskRoot) {
            return $result
        }
    } catch { }
    return $null
}

function Stop-ManagedApp {
    # Match both absolute paths and the exact script argument, not all Python processes.
    $expectedCommand = '^"?' + [regex]::Escape($taskPython) + '"?\s+"?' + [regex]::Escape($taskLauncher) + '"?\s*$'
    $processes = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
        Where-Object { $_.CommandLine -match $expectedCommand })
    foreach ($managedProcess in $processes) {
        Stop-Process -Id $managedProcess.ProcessId -ErrorAction SilentlyContinue
    }
    # Wait for the actual interpreter child to release its socket.
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        $remaining = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
            Where-Object { $_.CommandLine -match $expectedCommand })
        if ($remaining.Count -eq 0) { return }
        Start-Sleep -Milliseconds 100
    }
    throw 'The managed app did not stop. No replacement server was started.'
}

if ($Restart -or $Stop) { Stop-ManagedApp }
if ($Stop) {
    Write-Output 'Managed app stopped. Other processes were left untouched.'
    exit 0
}

$expectedFingerprint = (& $taskPython $taskLauncher --fingerprint | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Could not calculate the current source fingerprint.' }
$running = Get-AppStatus
if ($running) {
    if ($running.fingerprint -ne $expectedFingerprint) {
        throw 'The running app has older source files. Run .\start_app.ps1 -Restart.'
    }
    Write-Output "App ready: http://127.0.0.1:5000 [$($running.fingerprint)] PID $($running.pid)"
    exit 0
}
if ($Status) { throw 'No managed app is responding on port 5000.' }
if (Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Port 5000 is occupied by another server. Stop that server before starting this app.'
}

$taskLogFolder = Join-Path $taskRoot 'logs'
New-Item -ItemType Directory -Path $taskLogFolder -Force | Out-Null
$taskProcessId = (& $taskPython $taskLauncher --start-background | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Could not launch the background server.' }
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    $running = Get-AppStatus
    if ($running -and $running.fingerprint -eq $expectedFingerprint) {
        Write-Output "App ready: http://127.0.0.1:5000 [$($running.fingerprint)] PID $($running.pid)"
        exit 0
    }
    if (-not (Get-Process -Id ([int]$taskProcessId) -ErrorAction SilentlyContinue)) { break }
    Start-Sleep -Milliseconds 250
}
throw 'The app did not become ready. Check logs/local-server.log; no successful start was reported.'
