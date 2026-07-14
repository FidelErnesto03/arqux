#!/usr/bin/env bash
# =============================================================================
# arqux_session_gate.sh — Gate de arranque obligatorio transparente
# BLP-017: Governance Enforcement
#
# SIEMPRE presenta dashboard de workspace primero.
# El proyecto se resuelve DESPUES, cuando el Arquitecto lo elige.
# =============================================================================
set -euo pipefail

# Find workspace root (walk up from cwd to find .arqux/)
find_workspace() {
    local dir="${1:-$(pwd)}"
    while [ "$dir" != "/" ]; do
        if [ -d "$dir/.arqux" ]; then
            echo "$dir"
            return 0
        fi
        dir=$(dirname "$dir")
    done
    return 1
}

WORKSPACE=$(find_workspace "${1:-$(pwd)}")
if [ -z "$WORKSPACE" ]; then
    echo "⬡ alfred | WORKSPACE | ?"
    echo ""
    echo "❌ No .arqux/ found. Run: cd workspace && arqux init"
    exit 1
fi

cd "$WORKSPACE"

# --- Identity detection from greeting ---
AGENT_ID="${ARQUX_AGENT_ID:-alfred}"

KNOWN_AGENTS=$(python3 -c "
import sys
sys.path.insert(0, '$WORKSPACE/ARQUX/src')
from pathlib import Path
identities_dir = Path('$WORKSPACE') / '.arqux' / 'identities'
agents = []
if identities_dir.is_dir():
    for f in identities_dir.glob('*.cortex'):
        agents.append(f.stem)
print(' '.join(agents))" 2>&1)

if [ ! -t 0 ]; then
    FIRST_MSG=$(cat)
    for agent in $KNOWN_AGENTS; do
        if echo "$FIRST_MSG" | grep -qi "hola $agent\|saludos $agent\|pasame con $agent\|cambia a $agent"; then
            AGENT_ID="$agent"
            break
        fi
    done
fi

export ARQUX_AGENT_ID="$AGENT_ID"

# --- Bootstrap at WORKSPACE level (always first) ---
RESULT=$(python3 -c "
import sys, json, os
sys.path.insert(0, '$WORKSPACE/ARQUX/src')
os.environ['ARQUX_AGENT_ID'] = '$AGENT_ID'
from arqux.handlers.session import bootstrap
r = bootstrap(path='$WORKSPACE')
dashboard = r.fields.get('hcortex_dashboard', '')
ctx = r.fields.get('cortex_context', {})
print(json.dumps({
    'ok': r.profile == 'OUT-WORK',
    'kind': ctx.get('kind', '?'),
    'agent': os.environ.get('ARQUX_AGENT_ID', '?'),
    'dashboard': dashboard,
}))
" 2>&1) || {
    echo "❌ Bootstrap failed"
    exit 1
}

OK=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['ok'])")
KIND=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['kind'])")
DASHBOARD=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['dashboard'])")

if [ "$OK" != "True" ]; then
    echo "❌ Bootstrap error"
    exit 1
fi

# --- Always present workspace dashboard first ---
echo "⬡ $AGENT_ID | WORKSPACE | $WORKSPACE"
echo ""
echo "$DASHBOARD"
echo ""

# If already inside a project, note it but DON'T switch automatically
CWD=$(pwd)
if [ "$CWD" != "$WORKSPACE" ] && [ -d "$CWD/.arqux" ]; then
    PROJECT_NAME=$(basename "$CWD")
    echo "📍 Current directory: $PROJECT_NAME"
fi

echo "¿En qué proyecto trabajamos, Arquitecto?"

exit 0
