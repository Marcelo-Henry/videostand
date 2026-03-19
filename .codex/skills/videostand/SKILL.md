---
name: videostand
description: Resumir videos locais (.mp4) ou links do YouTube em modo local-first, sem depender de LLM por API para entender imagem/audio. Use quando Codex receber um video, URL do YouTube, ou quando o usuario pedir resumo/timeline de gravacao de tela, gameplay ou vinheta. O fluxo principal usa frames + transcricao local (faster-whisper) e a propria IA do Codex para interpretar os keyframes.
---

# VideoStand

Extrair frames representativos, transcrever audio localmente quando disponivel e preparar um pacote de revisao para a propria IA do Codex gerar o resumo final.

Priorizar amostragem por tempo (`--interval-seconds`) em videos longos. Usar `--every-n-frames` quando for necessario granularidade por frame.

## Quick Start

Definir o caminho da skill:

```bash
export VSUM="/home/marcelo/videostand/.codex/skills/videostand/scripts"
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
7. Abrir `review_keyframes/*.jpg` e `codex_review_pack.md` no proprio Codex.
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

## Performance Knobs

- `AUTO_SMART_SAMPLING=1` (padrao): escolhe automaticamente `INTERVAL_SECONDS`, `MAX_FRAMES` e `BATCH_SIZE` com base na duracao do video.
- `AUDIO_BACKEND=local` (padrao): usa transcricao local.
- `SUMMARY_BACKEND=codex-local` (padrao): prepara pack local para a IA do Codex.
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

## References

- Prompt base e variacoes: `references/prompt_templates.md`
