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

AXM:config_first{ The agent MUST create the MCP config file if it does not exist. The config file location depends on the platform. Without it, OpenCode/Claude/Cursor will not detect the MCP server. }

STP:config_locations{
  opencode:"Workspace root: <workspace>/opencode.json (priority). Also: ~/.config/opencode/opencode.jsonc (fallback).",
  claude:"~/.config/claude/claude_desktop_config.json (mcpServers key).",
  cursor:"~/.cursor/mcp.json (mcpServers key).",
  generic:"Platform-specific. See mcp.skill.md for JSON format.",
}

STP:mcp_json{
  format:"MCP JSON. Key and fields depend on platform:",
  standard:"Key: mcpServers. Fields: command, args, env. (Claude, Continue, Cursor)",
  opencode:"Key: mcp. Fields: type:local, command, args, enabled:true, environment. (OpenCode CLI)",
  example_standard:{
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
  example_opencode:{
    mcp:{
      arqux:{
        type:"local",
        command:"arqux",
        args:["serve"],
        enabled:true,
        environment:{
          ARQUX_AGENT_ID:"alfred",
          ARQUX_AGENT_ROLE:"governor"
        }
      }
    }
  },
  note:"Restart after config. Standard uses env, OpenCode uses environment."
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
