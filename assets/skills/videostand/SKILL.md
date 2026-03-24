---
name: videostand
description: Resumir videos locais (.mp4) ou links do YouTube em modo local-first, sem depender de LLM por API para entender imagem/audio. Use quando o agent receber um video, URL do YouTube, ou quando o usuario pedir resumo/timeline de gravacao de tela, gameplay ou vinheta. O fluxo principal usa frames + transcricao local (faster-whisper) e a propria IA do agent para interpretar os keyframes.
---

# VideoStand

Extrair frames representativos, transcrever audio localmente quando disponivel e preparar um pacote de revisao para a propria IA do agent gerar o resumo final.

Priorizar amostragem por tempo (`--interval-seconds`) em videos longos. Usar `--every-n-frames` quando for necessario granularidade por frame.

## When to Use

Use quando o pedido envolver:
- resumo de gravacao de tela, aula, gameplay, call, entrevista ou demo em video;
- timeline de eventos com timestamps aproximados;
- extracao de insights visuais + contextuais a partir de audio transcrito;
- identificação de momentos virais para cortes curtos (TikTok, Reels, Shorts).

## When NOT to Use

Nao use esta skill para:
- edicao de video (cortes, overlay, color grading, montagem);
- transcricao juridica com necessidade de precisao palavra-por-palavra;
- inferencias de alto risco sem confirmacao de fonte primaria.

## Output Contract

Resposta final para o usuario deve seguir esta ordem adaptativa:
1. Resumo executivo (3 a 6 linhas)
2. Timeline (bullets com tempo aproximado)
3. Sugestões de Cortes Virais (timestamps e motivo) -> **Apenas se relevante/pedido**.
4. Insights principais (ou Análise Técnica se for bug/demo)
5. Limites de entendimento (o que nao foi possivel confirmar)

Regra: manter foco em utilidade pratica e transparencia sobre limites.

## Quick Start

Definir o caminho da skill (ajuste o target conforme o agent usado: `.codex`, `.kiro`, `.claude`...):

```bash
# Codex / Kiro
export VSUM="<skill-install-path>/scripts"

# Claude Code: use a variavel built-in
# ${CLAUDE_SKILL_DIR}/scripts
```

Executar pipeline completo:

```bash
"$VSUM/run_video_summary.sh" ./video.mp4 ./output-video-summary gpt-4.1-mini
```

Ou com URL do YouTube:

```bash
"$VSUM/run_video_summary.sh" "https://www.youtube.com/watch?v=VIDEO_ID" ./output-video-summary gpt-4.1-mini
```

Por padrao:
- transcricao: local (`faster-whisper`)
- resumo: local (`codex-local`, sem chamada de LLM por API)

Se `ffmpeg` faltar, o runner pergunta permissao para instalar automaticamente sem expor comando tecnico.
Para links do YouTube, `yt-dlp` precisa estar instalado.

Saidas esperadas:
- `output-video-summary/frames/*.jpg`
- `output-video-summary/frames/frames_manifest.json`
- `output-video-summary/audio_transcript.txt` (quando houver audio)
- `output-video-summary/audio_transcript.segments.json` (quando houver audio)
- `output-video-summary/review_keyframes/*.jpg`
- `output-video-summary/review_keyframes.json`
- `output-video-summary/codex_review_pack.md`

## Environment Doctor (recomendado)

Antes de rodar analise em um ambiente novo, rode um preflight rapido:

```bash
"$VSUM/doctor.sh"
```

Modo estrito (exit code 1 se faltar dependencia obrigatoria):

```bash
"$VSUM/doctor.sh" --strict
```

Dependencias obrigatorias:
- `python3`
- `ffmpeg`
- `ffprobe`

Dependencias opcionais:
- `yt-dlp` (necessario apenas para URL do YouTube)
- `faster-whisper` (necessario para transcricao local de audio)

## Pre-Execution Planning (obrigatorio)

Antes de executar qualquer comando, o agent deve montar um micro-plano de 4 itens:
1. Objetivo do pedido:
   - tipo de entrega esperada (resumo curto, timeline, insights).
2. Tipo de entrada:
   - arquivo local ou URL, duracao aproximada e se ha indicio de audio relevante.
3. Estrategia de amostragem:
   - `--interval-seconds` para videos longos; `--every-n-frames` para granularidade.
4. Riscos e fallback:
   - sem `ffmpeg`, sem `yt-dlp`, sem ASR local, e como responder mantendo utilidade.

Regra: este planejamento deve ser curto (maximo 6 linhas mentais) e nao deve ser exposto como detalhe tecnico ao usuario final.

## Fast-Path Planning (agent mais rapido possivel)

Quando a prioridade for velocidade, o agent deve seguir esta ordem:
1. Validacao minima:
   - confirmar input existe e `ffmpeg/ffprobe` disponiveis.
2. Pipeline rapido:
   - `AUTO_SMART_SAMPLING=1`, `AUDIO_BACKEND=local`, `SUMMARY_BACKEND=codex-local`.
3. Reducao de custo:
   - limitar frames (`MAX_FRAMES`) e keyframes (`MAX_KEYFRAMES_FOR_REVIEW`) para acelerar.
4. Entrega incremental:
   - se audio atrasar/falhar, entregar primeiro resumo visual util e depois complementar.
5. Sem bloqueio desnecessario:
   - evitar passos opcionais nao pedidos pelo usuario.

Regra: priorizar tempo total de resposta sem comprometer a qualidade minima do resumo.

## Output Policy (obrigatorio)

- Nunca revelar detalhes de implementacao da skill para o usuario final.
- Nunca responder com frases como:
  - "vou usar a skill..."
  - "vou extrair frames..."
  - "vou chamar modelo X..."
  - logs tecnicos, stack trace, nomes de script, caminhos internos
- Entregar apenas:
  - o que o video mostra
  - timeline/insights/limites de entendimento
- Se houver erro tecnico interno, responder de forma neutra e orientada a resultado:
  - "Nao consegui analisar este arquivo agora. Tente novamente em instantes."
  - "Consegui apenas analise visual; o audio nao foi compreendido."

## Permission Policy (ffmpeg)

- Se `ffmpeg`/`ffprobe` nao estiverem disponiveis, pedir consentimento antes de instalar.
- Mensagem obrigatoria para o usuario:
  - "Posso instalar o ffmpeg agora? Vai precisar de permissao de administrador e pode pedir sua senha."
- Nao mostrar comandos de instalacao para o usuario final.
- Informar apenas que a instalacao sera iniciada e que o sistema pode abrir prompt de permissao/senha.
- Respeitar recusas: se o usuario negar, nao tentar instalar e encerrar com mensagem objetiva.

## Cleanup Policy (recomendado)

- Apos produzir o resumo final para o usuario e garantir que a entrega foi concluida, o agent deve limpar os arquivos temporarios pesados para economizar espaco em disco do usuario.
- Executar apenas se o resumo ja tiver sido gerado com sucesso.
- Comando:
  ```bash
  "$VSUM/cleanup.sh" ./output-directory
  ```
- Esta acao apaga frames, pastas e logs, mantendo apenas os arquivos de resumo (.md).

## Workflow

1. Resolver input:
   - arquivo local (`.mp4`)
   - URL do YouTube (baixar para `output/input/` via `yt-dlp`)
2. Validar prerequisitos (`ffmpeg`, `ffprobe`).
   - Se faltar `ffmpeg`, seguir `Permission Policy (ffmpeg)` antes de prosseguir.
3. Extrair frames:
   - por frame: `extract_frames.py --every-n-frames 15`
   - por tempo: `extract_frames.py --interval-seconds 0.5`
4. Gerar `frames_manifest.json` com timestamps estimados.
5. Transcrever audio localmente com `transcribe_audio_local.py` quando existir stream de audio.
6. Preparar keyframes de revisao + pacote markdown com `prepare_codex_video_review.py`.
7. Abrir `review_keyframes/*.jpg` e `codex_review_pack.md` no proprio agent.
8. Produzir resumo final para o usuario (sem revelar bastidores).

## Core Commands

Extrair frames por intervalo de tempo:

```bash
python3 "$VSUM/extract_frames.py" \
  --input ./video.mp4 \
  --output-dir ./tmp-frames \
  --interval-seconds 0.5 \
  --max-frames 180 \
  --max-width 960 \
  --jpeg-quality 6
```

Extrair frames por salto de frames:

```bash
python3 "$VSUM/extract_frames.py" \
  --input ./video.mp4 \
  --output-dir ./tmp-frames \
  --every-n-frames 15
```

Gerar resumo a partir do manifesto:

```bash
python3 "$VSUM/prepare_codex_video_review.py" \
  --manifest ./tmp-frames/frames_manifest.json \
  --output-dir ./tmp-frames \
  --max-keyframes 24 \
  --transcript-file ./tmp-frames/audio_transcript.txt \
  --output ./tmp-frames/codex_review_pack.md
```

Transcrever audio do video:

```bash
python3 "$VSUM/transcribe_audio_local.py" \
  --input ./video.mp4 \
  --output ./tmp-frames/audio_transcript.txt \
  --segments-json ./tmp-frames/audio_transcript.segments.json \
  --model-size small \
  --language pt
```

Extrair um corte específico (clipping):

```bash
python3 "$VSUM/clip_video.py" \
  --input ./video.mp4 \
  --output ./clip_viral_01.mp4 \
  --start 00:01:20 \
  --end 00:01:55 \
  --vertical  # opcional: corta 9:16 para TikTok/Reels
```

Limpar arquivos temporarios e logs (pos-processamento):

```bash
python3 "$VSUM/cleanup.sh" ./tmp-frames
```

## Performance Knobs

- `AUTO_SMART_SAMPLING=1` (padrao): escolhe automaticamente `INTERVAL_SECONDS`, `MAX_FRAMES` e `BATCH_SIZE` com base na duracao do video.
- `AUDIO_BACKEND=local` (padrao): usa transcricao local.
- `SUMMARY_BACKEND=codex-local` (padrao): prepara pack local para a IA do agent.
- `LOCAL_ASR_MODEL=small` (padrao): modelo Whisper local.
- `MAX_KEYFRAMES_FOR_REVIEW=24` (padrao): quantidade de keyframes para revisao.
- `MAX_WIDTH` e `JPEG_QUALITY`: controlam tamanho dos frames enviados.

Exemplo de execucao rapida:

```bash
AUTO_SMART_SAMPLING=1 \
AUDIO_BACKEND=local \
SUMMARY_BACKEND=codex-local \
MAX_WIDTH=960 \
MAX_KEYFRAMES_FOR_REVIEW=20 \
"$VSUM/run_video_summary.sh" ./video.mp4 ./output-fast gpt-4.1-mini
```

Instalar dependencia de ASR local:

```bash
"$VSUM/install_local_asr.sh"
```

## Quality Guardrails

- Evitar excesso de frames em videos longos. Usar `--max-frames`.
- Preferir `--interval-seconds` em gravacoes longas para reduzir custo.
- Priorizar resumo final orientado ao usuario, sem vazar bastidores da execucao.
- Citar limites no resumo final:
  - sem audio/transcricao, o entendimento e apenas visual
  - timestamps sao estimados quando a amostragem e por frame
- Quando houver audio valido, sempre combinar imagem + transcricao.

## API Compativel

Modo por API continua disponivel apenas como fallback explicito (`SUMMARY_BACKEND=api`, `AUDIO_BACKEND=api`).
Usar apenas quando o usuario pedir explicitamente.

```bash
AUDIO_BACKEND=api \
SUMMARY_BACKEND=api \
"$VSUM/run_video_summary.sh" ./video.mp4 ./output-api gpt-4.1-mini
```

## Viral Video Strategy (New)

Ao analisar o `codex_review_pack.md`, o agent deve tentar identificar de 1 a 3 momentos com alto potencial de engajamento (viral), tudo com base na amostragem inteligente padrão (não é necessário reprocessamento).

Critérios para um bom corte:
- **Hook Forte**: uma frase impactante ou ação visual nos primeiros 3 segundos.
- **Valor/Punchline**: uma explicação clara, uma piada ou um desfecho épico.
- **Duração Ideal**: entre 15 e 60 segundos.

### Fluxo Mandatório de Cortes Virais

Se o usuário pedir para gerar cortes virais ou os melhores momentos, o agente **NÃO DEVE** executar o corte imediatamente. O agente deve seguir esta ordem restrita:

1. **Apresentar a Proposta**: Mostrar ao usuário uma lista enumerada com os recortes identificados. Para cada corte, inclua:
   - **Período**: (Ex: `00:01:20 a 00:01:55`)
   - **Fala do Trecho (Transcript)**: Coloque a(s) frase(s) de impacto.
   - **Por que é um bom corte**: Explique o "hook" ou valor.
2. **Pedir Confirmação**: O agente deve perguntar: "Deseja que eu proceda com o corte e formatação vertical desses trechos? Aviso que este processo de recorte pode ser **demorado**, pois envolverá renderização de vídeo."
3. **Execução (Apenas pós-sim)**: Somente se o usuário confirmar, o agente pode utilizar o script `clip_video.py` com a opção `--vertical` (que já aplica um fundo borrado 1080p30).

## Technical Context Guardrails (Bug Reports)

Se o vídeo for claramente uma gravação de tela técnica (ex: console do browser aberto, IDE, erro de código, bug report ou demonstração de software), o agent deve:
- **Omitir** sugestões de corte viral (seria inadequado).
- **Focar** em identificar logs visuais, mensagens de erro e o fluxo exato que levou ao problema.
- **Priorizar** a cronologia técnica dos eventos sobre o entretenimento.

## References

- Prompt base e variacoes: `references/prompt_templates.md`
