# governance-bootstrap — Initialize a fresh workspace from scratch

## When to use
- You are the first agent in a new workspace.
- The human has just run `arqux init` for the first time.
- A previous workspace was deleted and you need to start over.

## What to do

1. **Verify workspace initialization.**
   Call `workspace.status`. If it returns `NOT_FOUND`, call `workspace.init`
   with the current path. You become governor by default.

2. **Register the first project.**
   Ask the human: "What is the name of the first project you want to govern?"
   Then call `project.init` with that name and the project path.
   This creates the project brain — the shared mind every agent bound to
   this project will read and write.

3. **Open the first cycle.**
   Call `cycle.create` with name `Bootstrap` and a description like
   `Initial cycle to bootstrap governance and onboard agents`.

4. **Onboard additional agents (if any).**
   For each additional agent, call `protocol.adopt` with the agent ID and
   role (`executor` or `auditor`). Then call `project.bind` to bind the
   agent to the project — this writes a session entry to the brain's
   `# SESSIONS` section, making the agent visible to other concurrent agents.

5. **Create the first tasks.**
   Call `task.create` for each initial task. Assign to executors via the
   `assignee` field.

6. **Confirm.**
   Call `workspace.status` and `project.status`. Confirm:
   - The workspace is active.
   - The project is registered.
   - The brain exists with all nine sections.
   - The cycle is open.
   - Tasks are visible.
   - The brain version is >0 (mutations have occurred).

## Examples

```
Agent: workspace.status  → NOT_FOUND (workspace not initialized)
Agent: workspace.init    → ok
Human: "The project is called atlas-api"
Agent: project.init name="atlas-api"
Agent: cycle.create name="Bootstrap" description="Initial setup"
Agent: protocol.adopt agent_id="jarvis" role="executor"
Agent: project.bind agent_id="jarvis" role="executor"
Agent: task.create obj="Set up CI pipeline" assignee="jarvis"
```

## References
- `AGENTS.md` §2 (How to detect Arqux)
- `AGENTS.md` §5 (Roles and permissions)
- `AGENTS.md` §9 (The project brain — shared mind for concurrent agents)
