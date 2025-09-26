# bootstrap.ps1
Write-Output "Bootstrap: starting..."

$sterlingPath = "C:\Program Files\Sterling\SterlingPro\Sterling.exe"
$maxWait = 60

if (Test-Path $sterlingPath) {
    Write-Output "Starting Sterling: $sterlingPath"
    Start-Process -FilePath $sterlingPath
    Start-Sleep -Seconds 2
} else {
    Write-Output "Sterling executable not found at $sterlingPath. Proceeding to start connector only."
}

# Wait for COM to be available (best-effort)
$waited = 0
$comReady = $false
while ($waited -lt $maxWait -and -not $comReady) {
    try {
        $null = New-Object -ComObject "Sterling.StiEvents"
        $comReady = $true
        Write-Output "COM object available."
    } catch {
        Start-Sleep -Seconds 2
        $waited += 2
    }
}

if (-not $comReady) {
    Write-Output "Warning: COM object not available after wait. Connector will still start; COM calls will fail until available."
}

Write-Output "Starting Python connector..."
cd C:\sterling\connector
python app.py