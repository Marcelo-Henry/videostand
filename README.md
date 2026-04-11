<div align="center">

<img src="https://img.shields.io/badge/VideoStand-CLI-FF6B35?style=for-the-badge&labelColor=1a1a2e" alt="VideoStand CLI" />

<br/>

<p>
  <a href="https://www.npmjs.com/package/videostand-skill"><img src="https://img.shields.io/npm/v/videostand-skill?style=for-the-badge&logo=npm&logoColor=white&color=CB3837" alt="npm version" /></a>
  <a href="https://www.npmjs.com/package/videostand-skill"><img src="https://img.shields.io/npm/dm/videostand-skill?style=for-the-badge&color=4A90D9" alt="npm downloads" /></a>
  <img src="https://img.shields.io/badge/node-%3E%3D18-339933?style=for-the-badge&logo=node.js&logoColor=white" alt="Node >= 18" />
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue?style=for-the-badge" alt="MIT License" /></a>
</p>

<p><strong>Install the VideoStand skill across 17 AI agents with a single command.</strong></p>

> **A Note on Versioning & V3 Maturity** 
> 
> First and foremost, I would like to apologize for the inconsistent version numbering used in previous releases. As VideoStand has evolved from a small utility into a standalone video intelligence tool, **v3.0.0** marks our official commitment to the **Semantic Versioning (SemVer)** standard. This major milestone serves as a fresh start and the new baseline for reliability, predictability, and performance. Thank you for your patience and for being part of this growth.

</div>

---

## ✨ Supported agents

| Agent          | Target        |
| -------------- | ------------- |
| Antigravity    | `agent`       |
| OpenAI Codex   | `codex`       |
| Kiro           | `kiro`        |
| Claude Code    | `claude`      |
| Cline          | `cline`       |
| Cursor         | `cursor`      |
| Continue       | `continue`    |
| Roo            | `roo`         |
| OpenHands      | `openhands`   |
| Qwen           | `qwen`        |
| GitHub Copilot | `copilot`     |
| Junie          | `junie`       |
| Kilocode       | `kilocode`    |
| CommandCode    | `commandcode` |
| Kode           | `kode`        |
| Mux            | `mux`         |
| Openclaw       | `openclaw`    |

---

## 🚀 Installation

**Global (recommended)**
```bash
npm install -g videostand-skill
```

**Without installing (npx)**
```bash
npx videostand-skill init codex
```

---

## ⚡ Quick Start

```bash
# Install for a specific agent (local)
videostand init codex

# Install globally (HOME)
videostand -g init claude

# Install for all agents at once
videostand init all

# Short alias — same behavior
vs init codex
```

---

## 📖 Commands

```
videostand init <target|all> [--force]      Install the skill
videostand -g init <target|all> [--force]   Install globally

videostand remove <target|all>              Remove the skill
videostand -g remove <target|all>           Remove globally

videostand status [target|all]              Show installation and sync status
videostand sync [target|all]                Update installed skills

videostand where <target|all>               Show installation path
videostand -g where <target|all>

videostand doctor [target|all] [--strict] [--fix] [--json]   Check dependencies
videostand -g doctor [target|all] [--strict] [--fix] [--json]

videostand --help
videostand --version  |  videostand -v
```

> **Alias:** all commands above work with `vs` instead of `videostand`.

---

## 📂 Where files are installed

| Mode                     | Path                            |
| ------------------------ | ------------------------------- |
| **Local** (without `-g`) | `./<target>/skills/videostand`  |
| **Global** (with `-g`)   | `~/.<target>/skills/videostand` |

**Examples:**
```
./.claude/skills/videostand     ← local
~/.claude/skills/videostand     ← global

./.codex/skills/videostand      ← local
~/.codex/skills/videostand      ← global
```

---

## 🩺 Preflight check (doctor)

Check dependencies before running the skill:

```bash
videostand doctor              # check general environment
videostand doctor codex        # check specific target
videostand -g doctor claude --strict
videostand doctor all --fix    # auto-install missing dependencies
videostand doctor all --json   # machine-readable output for CI
```

---

## 🔧 Practical examples

<details>
<summary><strong>Local installation</strong></summary>

```bash
videostand init codex
videostand init kiro
videostand init claude
videostand init all
```
</details>

<details>
<summary><strong>Global installation</strong></summary>

```bash
videostand -g init codex
videostand -g init kiro
videostand -g init claude
videostand -g init all --force
```
</details>

<details>
<summary><strong>Show paths</strong></summary>

```bash
videostand where codex
videostand -g where kiro
videostand where all
```
</details>

<details>
<summary><strong>Force overwrite</strong></summary>

```bash
videostand init codex --force
videostand -g init claude --force
```
</details>

<details>
<summary><strong>Check status & Sync</strong></summary>

```bash
videostand status all
videostand status codex
videostand sync all
videostand -g sync claude
```
</details>

<details>
<summary><strong>Remove skill</strong></summary>

```bash
videostand remove codex
videostand remove all
videostand -g remove all
```
</details>

---

## ❗ Troubleshooting

| Error                     | Solution                               |
| ------------------------- | -------------------------------------- |
| `Skill already exists...` | Use `--force` to overwrite             |
| `Missing target...`       | Provide one of the 17 targets or `all` |
| `Unknown option...`       | Run `videostand --help`                |

---

<div align="center">
  <sub>Made with ❤️ by Marcelo, Codex and Antigravity</sub>
</div>