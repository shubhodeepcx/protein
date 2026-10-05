Param(
    [switch]$Rebuild
)

Write-Host "Stopping processes on ports 8000 and 3000..."
$pids = Get-NetTCPConnection -LocalPort 8000,3000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($pid in $pids) {
    if ($pid -and (Get-Process -Id $pid -ErrorAction SilentlyContinue)) {
        try {
            Stop-Process -Id $pid -Force -ErrorAction Stop
            Write-Host "Stopped $pid"
        } catch {
            Write-Host "Failed to stop $pid: $($_)"
        }
    }
}

# Change to repo root (scripts folder's parent)
Set-Location (Join-Path $PSScriptRoot '..')

Write-Host "Running start.cmd -Rebuild..."
& .\start.cmd -Rebuild
