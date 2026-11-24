# Point the Onboarding Agent at Qwen3 8B on your own computer (Ollama), for this PowerShell window only.
# First, once:   ollama pull qwen3:8b
# Then run this with a dot and a space in front, so the settings stay in your window:
#     . .\scripts\use_ollama_qwen.ps1
Remove-Item Env:CREDASSURE_LLM_CA_CERT -ErrorAction SilentlyContinue
$env:CREDASSURE_LLM_BASE_URL = "http://localhost:11434/v1"
$env:CREDASSURE_LLM_MODEL    = "qwen3:8b"
$env:CREDASSURE_LLM_API_KEY  = "ollama"      # Ollama ignores the key, but one must be sent
$env:CREDASSURE_LLM_TIMEOUT  = "120"         # the first call loads the model and can be slow
Write-Host "Onboarding Agent now uses $($env:CREDASSURE_LLM_MODEL) at $($env:CREDASSURE_LLM_BASE_URL)"
