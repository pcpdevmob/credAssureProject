# The course's hosted Qwen3-8B endpoint.  Edit the two EDIT lines, then:  source scripts/use_course_qwen.sh
export CREDASSURE_LLM_BASE_URL="https://YOUR-GROUP-HOST:PORT/v1"     # EDIT
export CREDASSURE_LLM_CA_CERT="$HOME/Downloads/YOUR-GROUP-CERT.crt"  # EDIT
export CREDASSURE_LLM_MODEL="Qwen/Qwen3-8B"
export CREDASSURE_LLM_TIMEOUT="60"
export CREDASSURE_LLM_BACKOFF="2,4"
if [ -z "$CREDASSURE_LLM_API_KEY" ] || [ "$CREDASSURE_LLM_API_KEY" = "ollama" ]; then
  read -rsp "Paste your group's API key (not shown): " CREDASSURE_LLM_API_KEY; echo; export CREDASSURE_LLM_API_KEY
fi
echo "Onboarding Agent now uses $CREDASSURE_LLM_MODEL at $CREDASSURE_LLM_BASE_URL"
