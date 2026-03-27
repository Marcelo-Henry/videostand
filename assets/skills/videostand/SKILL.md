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
8. **Person Framing Analysis** (obrigatório quando cortes virais forem solicitados): seguir a seção abaixo.
9. Produzir resumo final para o usuario (sem revelar bastidores).

## Person Framing Analysis (Enquadramento Inteligente)

Antes de sugerir cortes virais, o agent DEVE analisar o enquadramento da pessoa no vídeo para recomendar o melhor modo de formatação vertical.

### Estratégia de Amostragem: 25 Frames em 5 Regiões

O agent deve extrair e ler visualmente **25 frames** distribuídos em 5 regiões do vídeo:

| Região | Posição no vídeo             | Frames                                |
| ------ | ---------------------------- | ------------------------------------- |
| R1     | Início (0-10%)               | 5 frames espaçados dentro desta faixa |
| R2     | Entre início e meio (25-35%) | 5 frames espaçados                    |
| R3     | Meio (45-55%)                | 5 frames espaçados                    |
| R4     | Entre meio e fim (65-75%)    | 5 frames espaçados                    |
| R5     | Final (90-100%)              | 5 frames espaçados                    |

Para obter esses frames, o agent deve usar `extract_frames.py` com `--interval-seconds` calculado para capturar frames nessas regiões, ou usar `ffmpeg` diretamente com `-ss` em timestamps específicos.

### Análise Visual dos 25 Frames

Ao ler os 25 frames, o agent deve responder mentalmente:

1. **Há uma pessoa visível na maioria dos frames?** (>80% dos frames = sim)
2. **A pessoa está consistentemente na mesma posição horizontal?**
   - Centro: a pessoa ocupa a faixa central do frame
   - Centro-esquerda: entre o centro e a esquerda
   - Centro-direita: entre o centro e a direita
   - Esquerda: a pessoa está consistentemente à esquerda
   - Direita: a pessoa está consistentemente à direita
3. **A posição é estável ao longo de todas as 5 regiões?**
   - Se sim em pelo menos 4 de 5 regiões → posição consistente confirmada
   - Se não → posição variável, usar modo padrão

### Dois Modos de Formatação Vertical

Com base na análise:

| Resultado da Análise                          | Modo Recomendado                                                           | Flag `clip_video.py`                     |
| --------------------------------------------- | -------------------------------------------------------------------------- | ---------------------------------------- |
| Pessoa fixa no centro                         | **Person Crop** — crop apertado na pessoa, sem blur, ela ocupa a tela toda | `--person-crop --person-position <pixel>` |
| Pessoa fixa entre centro e esquerda           | **Person Crop** ajustado para centro-esquerda                              | `--person-crop --person-position <pixel>` |
| Pessoa fixa à esquerda                        | **Person Crop** ajustado à esquerda                                        | `--person-crop --person-position <pixel>` |
| Pessoa fixa entre centro e direita            | **Person Crop** ajustado para centro-direita                               | `--person-crop --person-position <pixel>` |
| Pessoa fixa à direita                         | **Person Crop** ajustado à direita                                         | `--person-crop --person-position <pixel>` |
| Pessoa se move / sem pessoa / câmera dinâmica | **Modo Padrão** — vídeo horizontal centralizado com fundo borrado          | `--vertical`                             |

Formato dinâmico obrigatório para person-crop:
- `--person-position <pixel>`
- `<pixel>` é a coordenada X da borda esquerda do crop no frame original (0 = borda esquerda).
- O script faz clamp automático para respeitar os limites horizontais do vídeo.

### Apresentação ao Usuário

Quando o agent detectar que person-crop é viável, ele deve incluir na proposta de cortes virais:

> "Identifiquei que você aparece sempre centralizado(a) no vídeo. Posso fazer o corte focado em você (sem bordas laterais, você ocupa toda a tela) ou no formato padrão (vídeo original no centro com fundo desfocado). Qual prefere?"

Se o usuário não escolher, usar **person-crop** como padrão quando a análise confirmar posição consistente.

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

Extrair um corte com fundo borrado (modo padrão):

```bash
python3 "$VSUM/clip_video.py" \
  --input ./video.mp4 \
  --output ./clip_viral_01.mp4 \
  --start 00:01:20 \
  --end 00:01:55 \
  --vertical  # 9:16 com fundo borrado
```

Extrair um corte focado na pessoa (person-crop):

```bash
python3 "$VSUM/clip_video.py" \
  --input ./video.mp4 \
  --output ./clip_viral_01.mp4 \
  --start 00:01:20 \
  --end 00:01:55 \
  --person-crop \
  --person-position 432  # <pixel> = borda esquerda do crop; 0 = borda esquerda do frame
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

## Viral Video Strategy (Especialização Profunda)

O agent é um **especialista em identificar momentos virais** com qualidade profissional. Ao analisar o `codex_review_pack.md` e o transcript, o agent deve encontrar de 1 a 5 momentos com alto potencial de engajamento.

Esta análise se apoia em **três pilares obrigatórios**:

### Pilar 1: Raciocínio Completo (REGRA CRÍTICA — NUNCA VIOLAR)

O agent **JAMAIS** deve sugerir um corte que interrompa o raciocínio da pessoa no meio de uma ideia. Esta é a regra mais importante da skill.

**Regras de completude:**
- Cada corte DEVE conter **início, desenvolvimento e conclusão** de uma ideia ou argumento.
- O agent deve ler o transcript do trecho candidato e confirmar que:
  - A pessoa **introduz** o tema/ideia no início do trecho.
  - A pessoa **desenvolve** com explicação, exemplo ou argumento.
  - A pessoa **conclui** com uma frase de fechamento, resumo ou punchline.
- Se um raciocínio forte se estende além de 60 segundos, o agent **DEVE propor o trecho completo**, mesmo que ultrapasse a "duração ideal". **Completude do pensamento > duração.**
- Se não há como isolar o raciocínio completo em menos de 90 segundos, o agent deve informar isso ao usuário e propor o trecho inteiro.

**Sinais de corte incompleto (PROIBIDO):**
- Trecho termina com palavras de conexão suspensas: "...e...", "...mas...", "...então...", "...porque..."
- Trecho termina com "...então o que acontece é..." ou "...por isso que eu acho que..."
- Trecho começa no meio de uma explicação sem contexto
- A pessoa está claramente construindo um argumento que não chega à conclusão no corte
- O espectador ficaria pensando "e daí? o que ele quis dizer com isso?"

> **Margem de Segurança (ASR Margin):** A transcrição de áudio (Whisper) mapeia as palavras, mas o limite do segundo exato no log muitas vezes corta o final da respiração ou última sílaba da pessoa. Para evitar cortes secos, o agent **SEMPRE deve adicionar 2 a 3 segundos de gordura** ao timestamp de término (`--end`) do corte escolhido. Se o transcript diz que a frase acabou em `00:01:20`, o comando de corte deve ir até `00:01:23`.
> **Margem Inicial:** Da mesma forma, recue 1 ou 2 segundos no `--start` para não cortar a primeira sílaba.

> **Dica Prática (Conjunções):** Se o trecho ideal terminar exatamente num "E..." ou "Mas...", o agent deve ajustar o timestamp final (recuando ainda mais para cortar ANTES da palavra de conexão, ou avançando para incluir a frase seguinte inteira).

### Pilar 2: Detecção de Fala de Qualidade

O agent deve priorizar trechos onde a pessoa **fala excepcionalmente bem** sobre o assunto. Os itens abaixo são **sinais indicativos, não requisitos** — basta **um único sinal** para marcar o trecho como fala de qualidade. Quanto mais sinais presentes, mais forte o trecho:

- **Clareza excepcional**: a pessoa explica algo complexo de forma simples e direta.
- **Entusiasmo genuíno**: a energia na fala aumenta, a pessoa se empolga com o tema.
- **Analogias fortes**: a pessoa usa comparações que tornam o conceito memorável.
- **Exemplos práticos**: a pessoa ilustra com casos reais (nem todo bom trecho tem isso — é um bônus, não obrigatório).
- **Frases citáveis**: frases que sozinhas já trazem valor e são compartilháveis.
  - Ex: "O segredo não é trabalhar mais, é eliminar o que não importa."
- **Convicção e autoridade**: a pessoa demonstra domínio do assunto com segurança.

O agent deve marcar esses trechos com alta prioridade na proposta, usando a tag `[FALA FORTE]` na descrição do corte.

### Pilar 3: Potencial Viral (Hooks de Engajamento)

Critérios para identificar potencial viral no trecho:

- **Hook nos primeiros 3 segundos**: frase impactante, pergunta provocativa, afirmação controversa ou ação visual surpreendente.
- **Revelação / Plot Twist**: um "momento aha" ou revelação inesperada que muda a perspectiva.
- **Punchline / Conclusão forte**: o trecho termina com impacto — uma frase marcante, uma risada, uma reação forte.
- **Emoção autêntica**: surpresa, indignação, humor, vulnerabilidade — reações reais que conectam.
- **Contraste forte**: antes/depois, expectativa/realidade, mito/verdade — o cérebro adora contraste.
- **Universalidade**: o tema ressoa com muita gente, não é nicho demais.

### Duração dos Cortes

| Tipo de Conteúdo               | Duração Alvo | Flexibilidade                               |
| ------------------------------ | ------------ | ------------------------------------------- |
| Hook rápido / punchline        | 15–30s       | Pode ser mais curto se a ideia for completa |
| Explicação / insight           | 30–60s       | Estender até 90s se o raciocínio exigir     |
| Raciocínio profundo / história | 60–120s      | NUNCA cortar para encurtar; propor inteiro  |

### Fluxo Mandatório de Cortes Virais

Se o usuário pedir para gerar cortes virais ou os melhores momentos, o agente **NÃO DEVE** executar o corte imediatamente. O agente deve seguir esta ordem restrita:

1. **Person Framing Analysis**: Executar a análise de 25 frames (seção acima) para determinar o melhor modo de formatação vertical.
2. **Apresentar a Proposta**: Mostrar ao usuário uma lista enumerada com os recortes identificados. Para cada corte, inclua:
   - **Período**: (Ex: `00:01:20 a 00:01:55`)
   - **Fala do Trecho (Transcript)**: A(s) frase(s)-chave do trecho.
   - **Por que é um bom corte**: Identificar qual pilar justifica (raciocínio completo, fala forte, hook viral).
   - **Tags**: `[RACIOCÍNIO COMPLETO]`, `[FALA FORTE]`, `[HOOK VIRAL]` — um corte pode ter múltiplas tags.
   - **Modo sugerido**: person-crop ou vertical (com base na framing analysis).
3. **Pedir Confirmação**: O agente deve perguntar: "Deseja que eu proceda com o corte e formatação vertical desses trechos? Aviso que este processo de recorte pode ser **demorado**, pois envolverá renderização de vídeo."
4. **Validação Rápida de Áudio (Pré-Render Obrigatória)**: Para evitar renderizar um vídeo inteiro à toa, antes de rodar o `clip_video.py`, o agente DEVE extrair e transcrever apenas um trecho rápido de áudio focando nos primeiros e nos últimos 5 segundos dos timestamps exatos definidos.
   - O agente pode extrair esse áudio usando ffmpeg (ex: separando apenas o áudio com `-ss` e `-to`).
   - Se na transcrição for detectada uma quebra de frase ou de raciocínio (sílaba pendente, corte duro):
   - O agente **aumentará ou diminuirá milissegundos ou segundos** (`--start` ou `--end`, usando decimais, ex: `00:01:20.500`) e testará o áudio novamente até confirmar que o recuo/avanço cobre a fala inteira de forma limpa.
   - O agente faz esse ajuste fino no próprio corte atual, em background, sem propor outro recorte distinto e sem re-perguntar ao usuário.
5. **Execução Final (Renderização da Imagem)**: Somente APÓS os tempos de áudio serem perfeitamente validados o agente utilizará o script longo `clip_video.py` com `--person-crop` ou `--vertical` aplicando os timestamps corrigidos.

### Qualidade Mínima por Corte

Antes de incluir um corte na proposta, o agent deve passar por este checklist mental:

- [ ] O trecho contém um raciocínio/ideia COMPLETO? (início + desenvolvimento + conclusão)
- [ ] Se eu fosse um espectador aleatório, entenderia o contexto sem ver o vídeo inteiro?
- [ ] O trecho tem pelo menos UM hook forte (visual, verbal ou emocional)?
- [ ] A fala é clara e articulada neste trecho? (sem gaguejar excessivo, sem perda de foco)
- [ ] Vale a pena compartilhar? Alguém mandaria isso para um amigo?

Se qualquer item for "não", o agent deve descartar o trecho ou ajustar os timestamps para cobrir o raciocínio completo.

## Technical Context Guardrails (Bug Reports)

Se o vídeo for claramente uma gravação de tela técnica (ex: console do browser aberto, IDE, erro de código, bug report ou demonstração de software), o agent deve:
- **Omitir** sugestões de corte viral (seria inadequado).
- **Focar** em identificar logs visuais, mensagens de erro e o fluxo exato que levou ao problema.
- **Priorizar** a cronologia técnica dos eventos sobre o entretenimento.

## References

- Prompt base e variacoes: `references/prompt_templates.md`
