# PowerShell Script to start Waitress, ngrok, and display the public URL

# Get the directory where the script is located
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Write-Host "Project Directory: $scriptDir"

# --- Configuration ---
$venvPath = Join-Path $scriptDir ".venv"
$ngrokExePath = Join-Path $scriptDir "ngrok.exe"
$pythonExePath = Join-Path (Join-Path $venvPath "Scripts") "python.exe"
$appFilesDir = Join-Path $scriptDir "app_files"
$waitressPort = 5000
# --- End Configuration ---

# --- Pre-checks ---
if (-not (Test-Path $venvPath)) {
    Write-Error "Virtual environment not found at $venvPath. Please ensure it exists."
    Read-Host "Press Enter to exit"
    Exit 1
}
if (-not (Test-Path $pythonExePath)) {
    Write-Error "Python executable not found in virtual environment at $pythonExePath."
    Read-Host "Press Enter to exit"
    Exit 1
}
if (-not (Test-Path $ngrokExePath)) {
    Write-Error "ngrok.exe not found at $ngrokExePath. Please ensure it's in the project folder."
    Read-Host "Press Enter to exit"
    Exit 1
}

# --- Start Processes ---
Write-Host "Starting Waitress server in the background..."
# Start Waitress using the virtual environment's python
$waitressArgs = "-m waitress --host=0.0.0.0 --port=$waitressPort app:app"
$waitressProcess = Start-Process -FilePath $pythonExePath -ArgumentList $waitressArgs -WorkingDirectory $appFilesDir -NoNewWindow -PassThru
if (-not $waitressProcess) {
     Write-Error "Failed to start Waitress process."
     Read-Host "Press Enter to exit"
     Exit 1
}
Write-Host "Waitress process started (PID: $($waitressProcess.Id))."

Write-Host "Starting ngrok tunnel in the background..."
$ngrokArgs = "http $waitressPort --log=stdout" # Log ngrok output to console for debugging if needed
$ngrokProcess = Start-Process -FilePath $ngrokExePath -ArgumentList $ngrokArgs -WorkingDirectory $scriptDir -NoNewWindow -PassThru
if (-not $ngrokProcess) {
     Write-Error "Failed to start ngrok process. Make sure ngrok is authenticated ('ngrok config add-authtoken ...')."
     # Attempt to stop waitress if ngrok failed
     Stop-Process -Id $waitressProcess.Id -Force -ErrorAction SilentlyContinue
     Read-Host "Press Enter to exit"
     Exit 1
}
Write-Host "ngrok process started (PID: $($ngrokProcess.Id))."

# --- Get ngrok URL ---
Write-Host "Waiting for ngrok tunnel to establish..."
$ngrokApiUrl = "http://127.0.0.1:4040/api/tunnels" # Default ngrok API address
$publicUrl = $null
$maxRetries = 10
$retryDelaySeconds = 2

for ($i = 1; $i -le $maxRetries; $i++) {
    Start-Sleep -Seconds $retryDelaySeconds
    try {
        Write-Host "Attempting to query ngrok API (Attempt $i/$maxRetries)..."
        $response = Invoke-RestMethod -Uri $ngrokApiUrl -Method Get -TimeoutSec 5
        # Find the https tunnel URL
        $httpsTunnel = $response.tunnels | Where-Object { $_.proto -eq 'https' }
        if ($httpsTunnel) {
            $publicUrl = $httpsTunnel.public_url
            Write-Host "Successfully retrieved ngrok URL." -ForegroundColor Green
            break # Exit loop if successful
        } else {
             Write-Warning "ngrok API responded, but no HTTPS tunnel found yet."
        }
    } catch {
        Write-Warning "Failed to connect to ngrok API: $($_.Exception.Message). Retrying..."
    }
}

# --- Display Result ---
if ($publicUrl) {
    Write-Host "--------------------------------------------------" -ForegroundColor Cyan
    Write-Host "Your application should be accessible at:"
    Write-Host $publicUrl -ForegroundColor Yellow
    Write-Host "--------------------------------------------------" -ForegroundColor Cyan
    Write-Host "Leave this window open to keep the server and tunnel running."
    Write-Host "Close this window OR press Ctrl+C here to attempt stopping Waitress and ngrok."
} else {
    Write-Error "Could not retrieve ngrok URL after $maxRetries attempts."
    Write-Error "Check if ngrok started correctly and is not blocked by a firewall."
    # Attempt to stop background processes
    Write-Host "Attempting to stop background processes..."
    Stop-Process -Id $waitressProcess.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $ngrokProcess.Id -Force -ErrorAction SilentlyContinue
}

# Keep the script window open. When closed/stopped, try to clean up.
try {
    Read-Host -Prompt "Press Enter or close this window to stop the servers"
} finally {
    Write-Host "Stopping background processes..."
    Stop-Process -Id $waitressProcess.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $ngrokProcess.Id -Force -ErrorAction SilentlyContinue
    Write-Host "Processes stopped."
} 