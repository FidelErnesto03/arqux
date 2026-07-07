$0

# -- $0: MCP SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# STP   | step       | attrs      | M | Working        | Configuration step
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable rule
# IDN   | identity   | attrs      | B | Semantic       | Identifier


$1: MCP CONFIGURATION

IDN:mcp_config{ purpose:"Arqux MCP server. MANDATORY on first session. Agents MUST load and execute this skill before any governance operation." }

AXM:setup_required{ The agent MUST configure MCP before operating. Without MCP or CLI fallback, Arqux governance is unreachable. }

STP:env_config{
  ARQUX_AGENT_ID:"alfred (steward), jarvis (executor), heimdall (auditor), seshat (scribe). Default: anonymous.",
  ARQUX_AGENT_ROLE:"governor | executor | auditor. Default: governor (full access).",
}


$2: MCP JSON SETUP

STP:mcp_json{
  format:"Standard MCP JSON for any client:",
  example:{
    mcpServers:{
      arqux:{
        command:"arqux",
        args:["serve"],
        env:{
          ARQUX_AGENT_ID:"alfred",
          ARQUX_AGENT_ROLE:"governor"
        }
      }
    }
  },
  note:"Restart MCP client after configuration."
}


$3: VERIFICATION

STP:verify{
  1:"Restart MCP client after config.",
  2:"Test: workspace.status or blueprint.list — should return data.",
  3:"Test: identity.record lesson=test kind=process — should return OK.",
  4:"If PERMISSION_DENIED: check env vars. Restart server and client.",
}


$4: CLI FALLBACK

IDN:cli_fallback{ purpose:"Agents without MCP (terminal-only, Codex) use CLI.", setup:"export ARQUX_AGENT_ID=alfred ARQUX_AGENT_ROLE=governor", usage:"arqux call <handler> <key=value...>" }

AXM:no_mcp_no_write{ If neither MCP nor CLI work, HALT. Report to Architect. Do NOT bypass with direct file edits. }
