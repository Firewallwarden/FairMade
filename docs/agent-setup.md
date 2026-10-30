# FairMade agents in JetBrains AI Chat

Choose **Frontend Agent** in WebStorm or **Backend Agent** in PyCharm. Both use
Codex through the installed ACP adapter. Shared rules live in root `AGENTS.md`;
specialist context lives in `frontend/AGENTS.md` and `backend/AGENTS.md`.
There is no separate Shared Agent dropdown entry.

The supplied SharedAgent, FrontendAgent, and BackendAgent documents are the
basis for these instruction files. Git approval language has been reconciled
with the team's standing authorization: in-scope staging, commits, normal
feature-branch pushes, and PR creation/updates run without repeated approval.
Merges and rewriting remote history still require explicit approval.

## Register on each developer's machine

JetBrains registers custom dropdown entries in `~/.jetbrains/acp.json`, outside
the repository. Cloning instruction files alone does not register agents.
The display names come from `agent_servers` keys in that file. See the
[JetBrains ACP guide](https://www.jetbrains.com/help/ai-assistant/acp.html).

1. Install Codex through **Settings | Tools | AI Assistant | Agents** if needed.
2. Locate the installed Node executable and the Codex ACP package's
   `dist/index.js`. The current adapter package is `@agentclientprotocol/codex-acp`.
   Use absolute paths for your own IDE installation. Do not copy a teammate's
   username, IDE version, or binary paths.
3. From this feature worktree (or a checkout containing these files), run:

```powershell
./scripts/agents/Register-FairMadeAgents.ps1 `
  -NodePath 'C:/absolute/path/to/node.exe' `
  -AdapterPath 'C:/absolute/path/to/@agentclientprotocol/codex-acp/dist/index.js'
```

The script merges the two named entries, preserves unrelated settings and
agents, and backs up an existing configuration beside it before replacing it.
It rejects malformed JSON and unrelated agents already using those display
names. The checked-in `scripts/agents/acp.template.json` contains no credentials
or machine-specific paths. The script does not install dependencies or change
authentication, model choice, sandbox permissions, or MCP settings.

4. Open **AI Chat | menu | Add Custom Agent** to view the local configuration.
   Choose **Frontend Agent** or **Backend Agent** in a new chat. If the entries
   do not appear, restart the IDE. Sign in through the selected agent if asked;
   custom agent authentication may differ from the bundled Codex integration.
5. Open a checkout containing all three instruction files. Until this PR is
   merged, use its worktree; do not copy these changes into the primary worktree.
6. Send: "Identify your selected role, read the shared and specialist
   instructions, and summarize the Git permissions and directory ownership."
   Confirm the expected role and both instruction paths before application work.

## How role context is loaded

Each entry sets `FAIRMADE_AGENT_ROLE` and a short developer instruction through
the adapter's `CODEX_CONFIG` option. The root instructions also require reading
the environment role and explicitly loading the specialist file. This provides
role selection even when a chat begins at the checkout root. The adapter may
receive additional IDE instructions; shared and specialist files remain the
repository source of truth. See the
[adapter's runtime options](https://github.com/agentclientprotocol/codex-acp#runtime-options).

Codex instruction discovery follows the path from the repository root to the
session's working directory. A nested file is therefore explicitly loaded for
the selected role when starting at the root. See
[OpenAI's AGENTS.md documentation](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

Start a new chat when changing roles. Re-register if an IDE update moves the
Node or adapter files. Each developer configures their own machine. Registered
entries are user-level: use these FairMade roles with FairMade checkouts only.

Instructions define ownership; they do not sandbox frontend and backend into
separate filesystem permissions. IDE security controls remain active and may
still require approval independently of repository standing authorization.

## Check or remove registration

Run the offline configuration checks without making model calls:

```powershell
./scripts/agents/Test-AgentRegistration.ps1 `
  -NodePath 'C:/absolute/path/to/node.exe' `
  -AdapterPath 'C:/absolute/path/to/@agentclientprotocol/codex-acp/dist/index.js'
```

To unregister, remove only `Frontend Agent` and `Backend Agent` from the local
`agent_servers` object. Keep other entries and settings. The adjacent backup
can restore the previous configuration if no subsequent local changes need
to be retained. Never commit the personal ACP configuration or its backups.
