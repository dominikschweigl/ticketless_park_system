# HeyLoadTest-RPS.ps1
# Consistent TOTAL RPS using derived concurrency

$targetUrl = "http://3.89.58.94"
$duration = "60s"
$timeout = 30
$cpus = 6

# Observed per-worker throughput
$perWorkerRps = 5

# Desired TOTAL RPS levels
$totalRpsLevels = @(500, 1000, 2000, 3000, 4000, 4200, 4500, 4800, 5000)

$heyPath = "hey.exe"

foreach ($totalRps in $totalRpsLevels) {

    # Compute required concurrency
    $concurrency = [Math]::Ceiling($totalRps / $perWorkerRps)

    Write-Host "`n=== Running hey test at ~$totalRps RPS ==="    
    Write-Host "Target: $targetUrl | Duration: $duration | RPS: $totalRps | Concurrency cap: $concurrency | Per-worker RPS: $perWorkerRps | CPUs: $cpus`n"


    & $heyPath `
        -z $duration `
        -c $concurrency `
        -q $perWorkerRps `
        -t $timeout `
        -cpus $cpus `
        -disable-keepalive=false `
        $targetUrl

    Write-Host "`n=== Completed test at ~$totalRps RPS ===`n"
    Start-Sleep -Seconds 30
}
