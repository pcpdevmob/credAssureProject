# Switch the model off for this PowerShell window: the agent uses template explanations.
#     . .\scripts\use_template_only.ps1
Remove-Item Env:CREDASSURE_LLM_BASE_URL, Env:CREDASSURE_LLM_MODEL, Env:CREDASSURE_LLM_API_KEY, Env:CREDASSURE_LLM_CA_CERT -ErrorAction SilentlyContinue
Write-Host "Model switched off: template explanations only."
