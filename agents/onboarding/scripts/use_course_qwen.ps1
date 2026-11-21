# Point the Onboarding Agent at the course's hosted Qwen3-8B endpoint, for this PowerShell window only.
#     . .\scripts\use_course_qwen.ps1
# Edit the two lines marked EDIT with your group's URL and certificate path from the learner guide.
# The key is NOT stored in this file: you type it when asked, and it lives only in this window.
$env:CREDASSURE_LLM_BASE_URL = "https://YOUR-GROUP-HOST:PORT/v1"                       # EDIT, e.g. the URL for your group number
$env:CREDASSURE_LLM_CA_CERT  = "$env:USERPROFILE\Downloads\YOUR-GROUP-CERT.crt"         # EDIT, the .crt file you were given
$env:CREDASSURE_LLM_MODEL    = "Qwen/Qwen3-8B"
$env:CREDASSURE_LLM_TIMEOUT  = "60"
$env:CREDASSURE_LLM_BACKOFF  = "2,4"         # on 429/503 wait 2 s, then 4 s (at most two retries)
if (-not $env:CREDASSURE_LLM_API_KEY -or $env:CREDASSURE_LLM_API_KEY -eq "ollama") {
    $secure = Read-Host "Paste your group's API key (it will not be shown)" -AsSecureString
    $env:CREDASSURE_LLM_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
}
if (-not (Test-Path $env:CREDASSURE_LLM_CA_CERT)) { Write-Warning "Certificate not found: $env:CREDASSURE_LLM_CA_CERT" }
Write-Host "Onboarding Agent now uses $($env:CREDASSURE_LLM_MODEL) at $($env:CREDASSURE_LLM_BASE_URL)"
