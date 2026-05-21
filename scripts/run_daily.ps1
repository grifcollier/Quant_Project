# Daily basket trade runner — called by Windows Task Scheduler at 4:30pm ET
# Set ALPACA_API_KEY and ALPACA_SECRET_KEY as System environment variables
# (Control Panel > System > Advanced > Environment Variables) before scheduling.

$ROOT = Split-Path -Parent $PSScriptRoot
$PYTHON = (Get-Command python).Source
$SCRIPT = Join-Path $PSScriptRoot "daily_trade.py"
$LOG_DIR = Join-Path $ROOT "logs"

if (-not (Test-Path $LOG_DIR)) { New-Item -ItemType Directory -Path $LOG_DIR | Out-Null }

$date = Get-Date -Format "yyyy-MM-dd"
$log  = Join-Path $LOG_DIR "scheduler_$date.log"

"[$( Get-Date -Format 'HH:mm:ss' )] Task Scheduler triggered daily_trade.py" | Out-File $log -Append

# Dry-run by default. Change to --execute once you've confirmed signals look correct.
& $PYTHON $SCRIPT 2>&1 | Tee-Object -FilePath $log -Append

"[$( Get-Date -Format 'HH:mm:ss' )] Done." | Out-File $log -Append
