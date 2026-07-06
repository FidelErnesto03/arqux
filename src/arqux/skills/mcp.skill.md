$0

# -- $0: MCP SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# STP   | step       | attrs      | M | Working        | Configuration step
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable rule


$1: MCP CONFIGURATION (PLATFORM AGNOSTIC)

IDN:mcp_config{ purpose:"Arqux MCP server. Environment variables are optional. Default: governor (full access). Set explicitly for multi-agent setups." }

AXM:env_vars_mandatory{ ARQUX_AGENT_ID and ARQUX_AGENT_ROLE are recommended for explicit identity. Default without them: governor (full access). }

STP:env_config{
  ARQUX_AGENT_ID:"Agent identifier. Set to: alfred (steward), jarvis (executor), heimdall (auditor), seshat (scribe). Default: anonymous.",
  ARQUX_AGENT_ROLE:"governor | executor | auditor. Default: auditor. For governance: governor.",
}

STP:mcp_json{
  format:"Standard MCP JSON configuration for any client:",
  example:"""{
  "mcpServers": {
    "arqux": {
      "command": "arqux",
      "args": ["serve"],
      "env": {
        "ARQUX_AGENT_ID": "alfred",
        "ARQUX_AGENT_ROLE": "governor"
      }
    }
  }
}""",
  note:"The env block is REQUIRED. Without it, Arqux starts as auditor (read-only).",
}

AXM:no_env_no_write{ If handlers return PERMISSION_DENIED, check ARQUX_AGENT_ROLE. Default is governor — but if explicitly set to auditor, mutations are blocked. }


$2: VERIFICATION

STP:verify{
  1:"Restart MCP client after configuration changes.",
  2:"Test read: workspace.status or blueprint.list — should return data.",
  3:"Test write: identity.record lesson='test' kind=process — should return OK, not PERMISSION_DENIED.",
  4:"If PERMISSION_DENIED: check ARQUX_AGENT_ROLE=governor. Restart MCP server and client.",
}


$3: CLI FALLBACK

IDN:cli_fallback{ If MCP cannot be configured (Codex, terminal-only agents), use CLI: arqux call <handler> <key=value>... Environment variables must still be set. }

STP:cli_env{
  setup:"export ARQUX_AGENT_ID=alfred && export ARQUX_AGENT_ROLE=governor",
  usage:"arqux call workspace.status | arqux call blueprint.create obj='...' cycle=...",
}
