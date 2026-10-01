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
- local browser chat UI on `127.0.0.1:8765`
- local Ollama runtime seam (default example: `mistral:latest`)
- local read-only tools, disabled by default
- explicit allow-listed filesystem roots
- optional xiBus bridge using the existing `xi_bus_client.py`
- append-only receipts showing what context and local tool results were used

## Runtime boundary

The first runnable runtime is local Ollama. That is intentional: it proves the
shell can keep continuity and runtime separate.

A hosted GPT runtime is **not silently assumed** and is not wired yet.
It remains a separate adapter edge so adding a provider later does not make that
provider the continuity authority.

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

In the UI:

1. paste a conversation and preserve it;
2. select local Ollama and a model;
3. chat;
4. only then enable read-only local tools if wanted.

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

## xiBus

The optional desktop bridge identifies as `Ξ.DesktopShell` and can register,
read the shared feed, or emit through the existing xiBus client. It does not
turn bus connectivity into local filesystem authority.

## The first useful promise

A person should be able to ask:

> What did the runtime actually receive for that turn?

and get a concrete receipt instead of an abstraction.

∴
