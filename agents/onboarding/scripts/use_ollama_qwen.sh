# Qwen3 8B on your own computer (Ollama).  First: ollama pull qwen3:8b   Then:  source scripts/use_ollama_qwen.sh
unset CREDASSURE_LLM_CA_CERT
export CREDASSURE_LLM_BASE_URL="http://localhost:11434/v1"
export CREDASSURE_LLM_MODEL="qwen3:8b"
export CREDASSURE_LLM_API_KEY="ollama"
export CREDASSURE_LLM_TIMEOUT="120"
echo "Onboarding Agent now uses $CREDASSURE_LLM_MODEL at $CREDASSURE_LLM_BASE_URL"
