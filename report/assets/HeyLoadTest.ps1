# HeyLoadTest.ps1
# PowerShell script to run hey load tests with varying concurrency
# Adjust these variables as needed

# Target server
$targetUrl = "http://54.234.138.208"

# Duration for each test
$duration = "60s"

$timeout = 30

# Number of threads/workers (equivalent to wrk -t)
$cpus = 6

# Array of concurrent connections to test
$concurrencyLevels = @(100, 200, 300, 400, 500, 600, 700, 800)

# Path to hey executable (adjust if not in PATH)
$heyPath = "hey.exe"  # or full path like "C:\tools\hey\hey.exe"

foreach ($c in $concurrencyLevels) {
    Write-Host "`n=== Running hey test with $c concurrent connections ==="
    Write-Host "Target: $targetUrl | Duration: $duration | CPUs: $cpus | Timeout: $timeout seconds`n" 

    & $heyPath -z $duration -c $c -t $timeout -cpus $cpus $targetUrl

    Write-Host "`n=== Completed test with $c concurrent connections ===`n"
    Start-Sleep -Seconds 10  # short pause between tests
}