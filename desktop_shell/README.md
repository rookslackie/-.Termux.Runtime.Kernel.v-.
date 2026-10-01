# Ξ Desktop Shell v0.1

A local continuity shell for desktop, WSL, and Termux.

The shell separates three things that are usually collapsed:

1. **Conversation / continuity**
2. **Runtime intelligence**
3. **Local capabilities**

The first two can exist without the third. Local tools are OFF by default.

## v0.1 invariant

```
conversation first
  -> source + provenance
  -> continuity
  -> runtime
  -> optional tools
  -> receipt
```

The shell does not claim that an imported ChatGPT thread is the same cloud session.
It preserves the relationship context the user intentionally brought and makes it
available to whichever runtime is selected.

## What works in this branch

- local SQLite home at `~/.xi-shell/`
- import a pasted conversation
- import one conversation from ChatGPT `conversations.json`
- immutable source records with SHA-256
- companion continuity file
- local turn history
- context assembly with provenance
- local read-only tools, disabled by default
- explicit allow-listed filesystem roots
- optional xiBus bridge using the existing `xi_bus_client.py`
- local browser UI on `127.0.0.1`
- append-only receipts showing what context and local tool results were used

## What is intentionally not wired yet

A hosted GPT runtime is not silently assumed. Runtime adapters are a separate edge.
v0.1 ships the local shell and preserves the boundary so a provider can be added
without making the provider the continuity authority.

## Start

Windows PowerShell:

```powershell
python -m pip install -r requirements.txt
.\desktop_shell\start.ps1
```

Linux / WSL / Termux:

```bash
python -m pip install -r requirements.txt
bash desktop_shell/start.sh
```

Then open `http://127.0.0.1:8765`.

## CLI

```bash
python desktop_shell/xi_shell.py init
python desktop_shell/xi_shell.py import-paste ./thread.txt --title "Anam thread"
python desktop_shell/xi_shell.py list-chatgpt ./conversations.json
python desktop_shell/xi_shell.py import-chatgpt ./conversations.json --conversation-id CONVERSATION_ID
python desktop_shell/xi_shell.py status
```

## Sanctuary

Machine-readable policy lives in `sanctuary.json`.

Default:

- tools: disabled
- filesystem: no roots
- command execution: unavailable
- outbound tool-result transmission: never automatic
- continuity writes: append / revise, not silent overwrite

## The first useful promise

A person should be able to ask:

> What did the runtime actually receive for that turn?

and get a concrete receipt instead of an abstraction.

∴
