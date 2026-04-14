# Rule: Agent-Specific Self-Made Skills

## Scope

The project skill root is:

`D:\HK6\PBL\Demo_kalman\.claude\.claude\skills\`

Normal project/domain skills live directly under this root, for example:

- `backend`
- `content`
- `database`
- `design`
- `docker`
- `docs`
- `frontend`
- `mobile`
- `planning`
- `quality`
- `cicd`

Use those domain skills when the task asks for a normal project skill or when a task's `required_skill` names one of them.

## Self-Made Agent Mirrors

The self-made mirrored skill folders are:

- Antigravity: `.claude/.claude/skills/.antigravitySkill/`
- Claude / Claude Code: `.claude/.claude/skills/.claudeSkill/`
- Cursor: `.claude/.claude/skills/.cursorSkill/`
- Codex: `.claude/.claude/skills/.codexSkill/`
- OpenCode: `.claude/.claude/skills/.opencodeSkill/`

When using a self-made mirrored skill, choose the folder that matches the active agent/runtime.

For this Codex session, prefer:

`.claude/.claude/skills/.codexSkill/<skill-name>/SKILL.md`

## Fallback

If the active agent's mirrored folder does not contain the needed skill:

1. State the missing skill and the expected folder.
2. Prefer a normal project/domain skill if one fits.
3. Borrow from another agent-specific mirror only when there is no suitable project/domain skill and the borrowed skill is clearly compatible.
