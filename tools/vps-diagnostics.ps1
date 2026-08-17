$ErrorActionPreference = "Continue"

Write-Host "=================================================="
Write-Host " IDX AI AGENT - VPS PRODUCTION DIAGNOSTICS"
Write-Host "=================================================="
Write-Host ""

Write-Host "1. SYSTEMD STATUS"
Write-Host "=================================================="
ssh idx-vps "systemctl status idxbot --no-pager -l"
Write-Host ""

Write-Host "2. RECENT ERROR LOGS"
Write-Host "=================================================="
ssh idx-vps "journalctl -u idxbot --no-pager -n 150 -p warning..emerg"
Write-Host ""

Write-Host "3. RECENT APPLICATION LOGS"
Write-Host "=================================================="
ssh idx-vps "journalctl -u idxbot --no-pager -n 150"
Write-Host ""

Write-Host "4. GIT STATUS - PRODUCTION"
Write-Host "=================================================="
ssh idx-vps "cd /root/idx-ai-agent && git status --short --branch"
Write-Host ""

Write-Host "5. RECENT COMMITS"
Write-Host "=================================================="
ssh idx-vps "cd /root/idx-ai-agent && git log -8 --oneline --decorate"
Write-Host ""

Write-Host "6. PYTHON"
Write-Host "=================================================="
ssh idx-vps "if [ -x /root/idx-ai-agent/venv/bin/python ]; then /root/idx-ai-agent/venv/bin/python --version; else python3 --version; fi"
Write-Host ""

Write-Host "7. DISK"
Write-Host "=================================================="
ssh idx-vps "df -h /"
Write-Host ""

Write-Host "8. MEMORY"
Write-Host "=================================================="
ssh idx-vps "free -h"
Write-Host ""

Write-Host "9. PYTHON PROCESSES"
Write-Host "=================================================="
ssh idx-vps "ps aux | grep '[p]ython'"
Write-Host ""

Write-Host "10. DEPLOYMENT DIRECTORY"
Write-Host "=================================================="
ssh idx-vps "cd /root/idx-ai-agent && pwd && ls -lah | head -40"
Write-Host ""

Write-Host "=================================================="
Write-Host " END DIAGNOSTICS"
Write-Host "=================================================="