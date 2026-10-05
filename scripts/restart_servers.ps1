<#
.SYNOPSIS
    Stops whatever is listening on the API and web ports, then relaunches ProteoLens.

.PARAMETER Rebuild
    Force a fresh frontend production build before starting.

.EXAMPLE
    .\scripts\restart_servers.ps1
    .\scripts\restart_servers.ps1 -Rebuild
#>
[CmdletBinding()]
param(
    [switch]$Rebuild
)

$Ports = 8000, 3000

Write-Host "Stopping processes listening on ports $($Ports -join ', ')..."
$owners = Get-NetTCPConnection -LocalPort $Ports -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    Where-Object { $_ -gt 0 }

foreach ($procId in $owners) {
    if (Get-Process -Id $procId -ErrorAction SilentlyContinue) {
        # /T kills the whole tree: `npm start` runs next-server as a child.
        & taskkill.exe /PID $procId /T /F *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Stopped PID $procId"
        } else {
            Write-Host "Failed to stop PID ${procId} (exit code $LASTEXITCODE)"
        }
    }
}

# Give Windows a moment to release the sockets before launch.ps1 checks them.
$deadline = (Get-Date).AddSeconds(10)
while ((Get-Date) -lt $deadline -and
       (Get-NetTCPConnection -LocalPort $Ports -State Listen -ErrorAction SilentlyContinue)) {
    Start-Sleep -Milliseconds 300
}

$launch = Join-Path $PSScriptRoot 'launch.ps1'
if ($Rebuild) {
    Write-Host 'Relaunching with a fresh build...'
    & $launch -Rebuild
} else {
    Write-Host 'Relaunching...'
    & $launch
}
