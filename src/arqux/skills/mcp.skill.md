$0

# -- $0: MCP SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# STP   | step       | attrs      | M | Working        | Configuration step
# WRK   | work       | attrs      | B | Working        | Test result


$1: CONFIGURATION

STP:add{ action:"hermes mcp add arqux --command arqux --args serve", env:"ARQUX_AGENT_ID=alfred, ARQUX_AGENT_ROLE=governor", note:"If MCP is already configured, skip this step." }

STP:verify{ action:"hermes mcp test arqux", expected:"30 tools discovered, 0 errors", note:"If test fails, try hermes mcp remove arqux then re-add with correct args order." }


$2: TROUBLESHOOTING

WRK:no_tools{ symptom:"hermes mcp test succeeds but mcp_arqux_* tools not in toolset", fix:"Run /reload-mcp or restart the session." }

WRK:auth_error{ symptom:"Handler returns NOT_FOUND or PERMISSION_DENIED", fix:"Ensure ARQUX_AGENT_ROLE=governor is set in the MCP environment." }

WRK:stale_code{ symptom:"New features not available even after pip install", fix:"Restart the MCP server: the running process has the old code." }
