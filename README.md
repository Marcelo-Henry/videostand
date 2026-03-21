# VideoStand CLI

<p align="center">
  <a href="https://www.npmjs.com/package/videostand-skill"><img src="https://img.shields.io/npm/v/videostand-skill?style=for-the-badge&logo=npm" alt="npm version"></a>
  <a href="https://www.npmjs.com/package/videostand-skill"><img src="https://img.shields.io/npm/dm/videostand-skill?style=for-the-badge" alt="npm downloads"></a>
  <img src="https://img.shields.io/badge/node-%3E%3D18-339933?style=for-the-badge&logo=node.js&logoColor=white" alt="Node >= 18">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue?style=for-the-badge" alt="MIT License"></a>
</p>

CLI para instalar a skill **VideoStand** no **Codex**, no **Kiro** e no **Claude Code**, com suporte a instalação **local** e **global**.

Alias rapido disponivel: `vs` (mesmo comportamento de `videostand`).

## O que este pacote faz

1. Copia a skill `videostand` já pronta para a estrutura correta do agent.
2. Permite escolher `codex`, `kiro` ou `claude` como target.
3. Permite instalar no projeto atual (`./`) ou no home do usuário (`~/`) com `-g`.

## Instalação

### Global

```bash
npm install -g videostand-skill
```

### Sem instalar globalmente (npx)

```bash
npx videostand-skill init codex
```

## Quick Start

```bash
# 1) Instalar skill local para Codex no projeto atual
videostand init codex

# 2) Instalar skill global para Codex
videostand -g init codex

# 3) Instalar skill local para Kiro
videostand init kiro

# 4) Instalar skill local para Claude Code
videostand init claude

# 5) Mesmo comando usando alias curto
vs init codex
```

## Comandos

```bash
videostand init <codex|kiro|claude|all> [--force]
videostand -g init <codex|kiro|claude|all> [--force]

videostand where <codex|kiro|claude|all>
videostand -g where <codex|kiro|claude|all>
videostand doctor [codex|kiro|claude|all] [--strict] [--json]
videostand -g doctor [codex|kiro|claude|all] [--strict] [--json]

videostand --help
videostand --version
videostand -v

# Alias curto equivalente
vs init <codex|kiro|claude|all> [--force]
vs -g init <codex|kiro|claude|all> [--force]
vs where <codex|kiro|claude|all>
vs -g where <codex|kiro|claude|all>
vs doctor [codex|kiro|claude|all] [--strict] [--json]
vs -g doctor [codex|kiro|claude|all] [--strict] [--json]
vs --help
vs --version
vs -v
```

## Preflight check

Use o doctor para verificar dependencias antes de rodar a skill:

```bash
videostand doctor
videostand doctor codex
videostand -g doctor claude --strict
videostand doctor all --json
```

## Como funciona

```text
1) Você escolhe target: codex, kiro ou claude
2) Você escolhe modo:
   - sem -g: instala local no diretório atual
   - com -g: instala global no HOME
3) O CLI copia os arquivos da skill para:
   - ./.<target>/skills/videostand
   - ~/.<target>/skills/videostand
```

## Modos de instalação

### Modo local (sem `-g`)

Instala no diretório em que você executou o comando:

```bash
./.codex/skills/videostand
./.kiro/skills/videostand
./.claude/skills/videostand
```

### Modo global (`-g`)

Instala no HOME do usuário:

```bash
~/.codex/skills/videostand
~/.kiro/skills/videostand
~/.claude/skills/videostand
```

## Exemplos práticos

```bash
# Instala local para Codex
videostand init codex

# Instala local para Kiro
videostand init kiro

# Instala local para Claude Code
videostand init claude

# Instala global para Codex
videostand -g init codex

# Instala global para Kiro
videostand -g init kiro

# Instala global para Claude Code
videostand -g init claude

# Instala para todos os targets de uma vez
videostand init all
videostand -g init all --force

# Força sobrescrita
videostand init codex --force
videostand -g init kiro --force
videostand init claude --force

# Ver caminhos
videostand where codex
videostand -g where kiro
videostand where claude
videostand where all

# Doctor machine-readable (CI/scripts)
videostand doctor all --json
```

## Troubleshooting

1. `Skill already exists...`
   - Use `--force` para sobrescrever.

2. `Missing target...`
   - Informe o target: `codex`, `kiro` ou `claude`.

3. `Unknown option...`
   - Rode `videostand --help` e use apenas as opções suportadas.

## Desenvolvimento

```bash
# Teste e2e do instalador
npm run test:e2e
```
