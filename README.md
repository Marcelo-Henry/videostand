# VideoStand Skill (Codex & Kiro)

CLI npm para instalar a skill **VideoStand** no Codex ou Kiro, em modo local ou global.

## Instalação

### Opção 1: instalar localmente para testar

```bash
npm install -g .
```

### Opção 2: usar com npx (quando publicado no npm)

```bash
npx videostand-skill init codex
```

## Uso

```bash
# Instala localmente em ./.codex/skills/videostand
videostand init codex

# Instala localmente em ./.kiro/skills/videostand
videostand init kiro

# Instala globalmente em ~/.codex/skills/videostand
videostand -g init codex

# Instala globalmente em ~/.kiro/skills/videostand
videostand -g init kiro

# Sobrescreve uma instalação existente (local ou global)
videostand init codex --force
videostand -g init kiro --force

# Mostra caminho local
videostand where codex
videostand where kiro

# Mostra caminho global
videostand -g where codex
videostand -g where kiro
```

## Caminho de instalação

Por padrão, `videostand init <target>` instala em:

```bash
./.<target>/skills/videostand
```

Com `-g`, instala em:

```bash
~/.<target>/skills/videostand
```

Onde `<target>` é `codex` ou `kiro`.

## Desenvolvimento

```bash
# Teste e2e do instalador
npm run test:e2e
```
