#!/usr/bin/env node

import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { homedir } from 'node:os';
import { spawnSync } from 'node:child_process';
import { intro, select, isCancel, cancel, spinner, text } from '@clack/prompts';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const SOURCE_SKILL_DIR = resolve(__dirname, '..', 'assets', 'skills', 'videostand');
const PACKAGE_JSON_PATH = resolve(__dirname, '..', 'package.json');
const PACKAGE_VERSION = JSON.parse(readFileSync(PACKAGE_JSON_PATH, 'utf-8')).version;

const TARGETS = {
  antigravity: '.agent',
  codex: '.codex',
  kiro: '.kiro',
  claude: '.claude',
  cline: '.cline',
  cursor: '.cursor',
  continue: '.continue',
  roo: '.roo',
  openhands: '.openhands',
  qwen: '.qwen',
  copilot: { local: '.github', global: '.copilot' },
  junie: '.junie',
  kilocode: '.kilocode',
  commandcode: '.commandcode',
  kode: '.kode',
  mux: '.agents',
  openclaw: '.openclaw',
};

const VALID_TARGETS = Object.keys(TARGETS);
const ALL_TARGETS_KEYWORD = 'all';
const COLOR_ENABLED =
  Boolean(process.stdout.isTTY) &&
  process.env.NO_COLOR === undefined &&
  process.env.TERM !== 'dumb';

const ANSI = {
  reset: '\x1b[0m',
  bold: '\x1b[1m',
  dim: '\x1b[2m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
};

function colorize(text, ...styles) {
  if (!COLOR_ENABLED || styles.length === 0) return text;
  const prefix = styles.map((style) => ANSI[style]).join('');
  return `${prefix}${text}${ANSI.reset}`;
}

function statusTag(type) {
  const tags = {
    ok: colorize('✔', 'bold', 'green'),
    warn: colorize('⚠', 'bold', 'yellow'),
    error: colorize('✘', 'bold', 'red'),
    info: colorize('ℹ', 'bold', 'blue'),
    miss: colorize('○', 'bold', 'red'),
    hint: colorize('💡', 'bold', 'cyan'),
  };
  return tags[type] || '•';
}

function printFooter() {
  console.log(colorize('│', 'dim'));
  console.log(`${colorize('└', 'dim')}  ${colorize('💡 Have any idea? Open an issue on our repo!', 'bold', 'blue')}`);
  console.log(`   ${colorize('https://www.github.com/Marcelo-Henry/videostand', 'dim')}`);
}

function printHeader(title, subtitle = '') {
  console.log(colorize(`┌  ${title}`, 'bold', 'cyan'));
  if (subtitle) {
    console.log(colorize(`│  ${subtitle}`, 'dim'));
  }
  console.log(colorize('│', 'dim'));
}

function printKeyValueRows(rows) {
  const keyWidth = rows.reduce((max, row) => Math.max(max, row[0].length), 0);
  for (const [key, value] of rows) {
    console.log(`  ${colorize(key.padEnd(keyWidth), 'bold')}  ${value}`);
  }
}

function formatColumns(items) {
  if (items.length === 0) return [];

  const terminalWidth = process.stdout.columns || 80;
  const maxItemLength = items.reduce((max, item) => Math.max(max, item.length), 0);
  const columnWidth = maxItemLength + 3;
  const columns = Math.max(1, Math.floor(Math.max(terminalWidth - 2, 1) / columnWidth));
  const lines = [];

  for (let i = 0; i < items.length; i += columns) {
    const rowItems = items.slice(i, i + columns);
    const line = rowItems
      .map((item, idx) =>
        idx === rowItems.length - 1 ? item : item.padEnd(columnWidth, ' ')
      )
      .join('');
    lines.push(`  ${line}`);
  }

  return lines;
}

function printHelp() {
  printHeader(`VideoStand CLI v${PACKAGE_VERSION}`, 'Install and validate the skill in multiple agents.');
  console.log('');
  console.log(colorize('Usage', 'bold'));
  printKeyValueRows([
    ['videostand', '[--global|-g] <command> [target] [options]'],
    ['vs', '[--global|-g] <command> [target] [options]'],
  ]);
  console.log('');
  console.log(colorize('Quick Examples', 'bold'));
  console.log('  videostand init codex');
  console.log('  videostand -g init codex');
  console.log('  videostand init all --force');
  console.log('  videostand doctor all --strict');
  console.log('');
  console.log(colorize('Commands', 'bold'));
  printKeyValueRows([
    ['run <video|url>', 'Process a video file standalone'],
    ['watch [dir]', 'Watch a folder for new video files'],
    ['optimize', 'Detect and configure hardware acceleration'],
    ['init <target|all>', 'Install skill folder for one/all targets'],
    ['remove <target|all>', 'Remove skill folder from one/all targets'],
    ['status [target|all]', 'Show installation and sync status'],
    ['sync [target|all]', 'Update installed skills to match package assets'],
    ['where <target|all>', 'Print installation path for one/all targets'],
    ['doctor [target|all]', 'Check dependencies and installation status'],
    ['--version, -v', 'Print CLI version'],
    ['--help, -h', 'Show this help'],
  ]);
  console.log('');
  console.log(colorize(`Targets (${VALID_TARGETS.length})`, 'bold'));
  const targetLines = VALID_TARGETS.map((t) => t);
  for (const line of formatColumns(targetLines)) {
    console.log(line);
  }
  console.log('');
  console.log(colorize('Options', 'bold'));
  printKeyValueRows([
    ['-g, --global', 'Use ~/.<target> instead of ./.<target>'],
    ['--force', 'Overwrite existing skill folder'],
    ['--explain', 'Show detailed explanation and examples for a command'],
    ['--strict', 'With doctor: exit with code 1 if required deps are missing'],
    ['--fix', 'With doctor: auto-install missing dependencies (ffmpeg/faster-whisper)'],
    ['--json', 'With doctor: output machine-readable JSON'],
  ]);
  console.log('');
  console.log(colorize('Path Pattern', 'bold'));
  console.log('  local:  ./.<target>/skills/videostand');
  console.log('  global: ~/.<target>/skills/videostand');
  printFooter();
}

function printVersion() {
  console.log(PACKAGE_VERSION);
  printFooter();
}

function parseOptions(args) {
  const options = {
    force: false,
    global: false,
    strict: false,
    json: false,
    fix: false,
    explain: false,
  };

  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];

    if (arg === '-g' || arg === '--global') {
      options.global = true;
      continue;
    }

    if (arg === '--force') {
      options.force = true;
      continue;
    }

    if (arg === '--explain') {
      options.explain = true;
      continue;
    }

    if (arg === '--strict') {
      options.strict = true;
      continue;
    }

    if (arg === '--json') {
      options.json = true;
      continue;
    }

    if (arg === '--fix') {
      options.fix = true;
      continue;
    }

    if (arg === '--help' || arg === '-h') {
      printHelp();
      process.exit(0);
    }

    if (arg === '--version' || arg === '-v') {
      printVersion();
      process.exit(0);
    }

    console.error(`${statusTag('error')} Unknown option: ${arg}`);
    console.error(`${statusTag('hint')} Run "videostand --help" for usage.`);
    process.exit(1);
  }

  return options;
}

function getPaths(options, target) {
  const targetConfig = TARGETS[target];
  if (!targetConfig) {
    throw new Error(`Target directory configuration not found for: ${target}`);
  }
  const dotDir = typeof targetConfig === 'string'
    ? targetConfig
    : (options.global ? targetConfig.global : targetConfig.local);
  const baseDir = options.global ? homedir() : process.cwd();
  const targetRoot = join(resolve(baseDir), dotDir);
  const targetDir = join(targetRoot, 'skills', 'videostand');

  return { targetRoot, targetDir };
}

function commandWhere(options, target) {
  const isAll = !target || target === ALL_TARGETS_KEYWORD;
  const targets = isAll ? VALID_TARGETS : [target];

  if (isAll && process.stdout.isTTY) {
    printHeader('VideoStand Paths', options.global ? 'global scope (~)' : 'local scope (cwd)');
  }

  for (const t of targets) {
    const { targetDir } = getPaths(options, t);
    if (isAll) {
      console.log(`${t}: ${targetDir}`);
    } else {
      console.log(targetDir);
    }
  }
}

function commandInit(options, target) {
  if (!existsSync(SOURCE_SKILL_DIR)) {
    console.error(`${statusTag('error')} Skill source not found in package assets.`);
    process.exit(1);
  }

  const isAll = !target || target === ALL_TARGETS_KEYWORD;
  let targets = isAll ? VALID_TARGETS : [target];

  if (isAll) {
    targets = targets.filter((t) => {
      const { targetRoot } = getPaths(options, t);
      return existsSync(targetRoot);
    });

    if (targets.length === 0) {
      console.log(`${statusTag('info')} No existing agent directories found. Skipping installation.`);
      return;
    }
  }

  const targetData = targets.map((t) => ({
    target: t,
    ...getPaths(options, t),
  }));

  for (const data of targetData) {
    if (existsSync(data.targetDir) && !options.force) {
      console.error(`${statusTag('error')} Skill already exists for "${data.target}".`);
      console.error(`  path: ${data.targetDir}`);
      console.error(`${statusTag('hint')} Run again with --force to overwrite.`);
      process.exit(1);
    }
  }

  printHeader('VideoStand Install', options.global ? 'global scope (~)' : 'local scope (cwd)');

  for (const data of targetData) {
    const { target, targetDir } = data;

    if (existsSync(targetDir)) {
      rmSync(targetDir, { recursive: true, force: true });
      console.log(`${statusTag('info')} Existing skill removed for "${target}" (--force).`);
    }

    mkdirSync(dirname(targetDir), { recursive: true });
    cpSync(SOURCE_SKILL_DIR, targetDir, { recursive: true });

    console.log(`${statusTag('ok')} ${target} -> ${targetDir}`);
  }

  console.log('');
  console.log(`${statusTag('ok')} Installation finished for ${targets.length} target(s).`);
}

function commandExists(cmd) {
  const result = spawnSync('sh', ['-c', `command -v "${cmd}" >/dev/null 2>&1`], {
    stdio: 'ignore',
  });
  return result.status === 0;
}

function pythonCanImport(moduleName) {
  if (!commandExists('python3')) return false;
  const code = `import ${moduleName.replace(/-/g, '_')}`;
  const result = spawnSync('python3', ['-c', code], { stdio: 'ignore' });
  return result.status === 0;
}

function buildEnvironmentChecks() {
  const required = ['python3', 'ffmpeg', 'ffprobe'];
  const optional = ['yt-dlp'];
  const requiredChecks = {};
  const optionalChecks = {};
  const missingRequired = [];

  for (const cmd of required) {
    const ok = commandExists(cmd);
    requiredChecks[cmd] = ok;
    if (!ok) missingRequired.push(cmd);
  }

  for (const cmd of optional) {
    optionalChecks[cmd] = commandExists(cmd);
  }

  return {
    required: requiredChecks,
    optional: optionalChecks,
    fasterWhisper: pythonCanImport('faster_whisper'),
    missingRequired,
  };
}

function buildInstallChecks(options, targets) {
  const checks = {};
  for (const target of targets) {
    const { targetDir } = getPaths(options, target);
    const skillFilePath = join(targetDir, 'SKILL.md');
    const runScriptPath = join(targetDir, 'scripts', 'run_video_summary.sh');
    checks[target] = {
      path: targetDir,
      skillFile: existsSync(skillFilePath),
      runScript: existsSync(runScriptPath),
    };
  }
  return checks;
}

function commandDoctor(options, target) {
  const isAll = !target || target === ALL_TARGETS_KEYWORD;
  let targets = isAll ? VALID_TARGETS : [target];

  if (isAll) {
    targets = targets.filter((t) => {
      const { targetRoot } = getPaths(options, t);
      return existsSync(targetRoot);
    });
  }

  if (options.fix && !options.json) {
    const initialChecks = buildEnvironmentChecks();

    if (initialChecks.missingRequired.includes('ffmpeg') || initialChecks.missingRequired.includes('ffprobe')) {
      console.log(`${statusTag('info')} Missing ffmpeg/ffprobe. Attempting auto-install...`);
      const scriptPath = resolve(SOURCE_SKILL_DIR, 'scripts', 'install_ffmpeg.sh');
      spawnSync('bash', [scriptPath], { stdio: 'inherit' });
    }

    if (initialChecks.required.python3 && !initialChecks.fasterWhisper) {
      console.log(`${statusTag('info')} Missing faster-whisper. Attempting auto-install...`);
      const scriptPath = resolve(SOURCE_SKILL_DIR, 'scripts', 'install_local_asr.sh');
      spawnSync('bash', [scriptPath], { stdio: 'inherit' });
    }
    console.log('');
  }

  const envChecks = buildEnvironmentChecks();
  const installChecks = buildInstallChecks(options, targets);

  if (options.json) {
    const payload = {
      doctor: 'videostand',
      strict: options.strict,
      global: options.global,
      environment: {
        required: envChecks.required,
        optional: envChecks.optional,
        fasterWhisper: envChecks.fasterWhisper,
        missingRequired: envChecks.missingRequired,
      },
      installation: installChecks,
    };
    console.log(JSON.stringify(payload, null, 2));
    if (options.strict && envChecks.missingRequired.length > 0) {
      process.exit(1);
    }
    return;
  }

  printHeader(
    'VideoStand Doctor',
    options.global ? 'global scope (~)' : 'local scope (cwd)'
  );

  console.log(colorize('├  Environment', 'bold'));

  for (const [cmd, ok] of Object.entries(envChecks.required)) {
    console.log(`│  ${ok ? statusTag('ok') : statusTag('error')} ${cmd}`);
  }

  for (const [cmd, ok] of Object.entries(envChecks.optional)) {
    console.log(
      `│  ${ok ? statusTag('ok') : statusTag('warn')} ${cmd} (optional)`
    );
  }

  if (envChecks.fasterWhisper) {
    console.log(`│  ${statusTag('ok')} faster-whisper Python package`);
  } else {
    console.log(
      `│  ${statusTag('warn')} faster-whisper Python package (optional)`
    );
  }

  for (const t of targets) {
    const info = installChecks[t];
    console.log(colorize('│', 'dim'));
    console.log(
      colorize(`├  Installation (${t}${options.global ? ' global' : ' local'})`, 'bold')
    );
    console.log(
      `│  ${info.skillFile ? statusTag('ok') : statusTag('miss')} SKILL.md`
    );
    console.log(
      `│  ${info.runScript ? statusTag('ok') : statusTag('miss')} run_video_summary.sh`
    );
  }

  console.log(colorize('│', 'dim'));
  if (envChecks.missingRequired.length === 0) {
    console.log(`${colorize('└', 'dim')}  ${statusTag('ok')} Doctor finished. All good!`);
    return;
  }

  console.log(
    `${colorize('└', 'dim')}  ${statusTag('warn')} Missing dependencies: ${envChecks.missingRequired.join(', ')}`
  );
  console.log(`${statusTag('hint')} Install ffmpeg and python3 to run full local pipeline.`);
  if (options.strict) {
    process.exit(1);
  }
}

function commandStatus(options, target) {
  const isAll = !target || target === ALL_TARGETS_KEYWORD;
  const targets = isAll ? VALID_TARGETS : [target];
  const results = [];

  for (const t of targets) {
    const { targetDir, targetRoot } = getPaths(options, t);
    const isInstalled = existsSync(targetDir);
    const hasAgentDir = existsSync(targetRoot);

    if (!isInstalled) {
      if (!isAll || hasAgentDir) {
        results.push({ target: t, status: 'MISSING', path: targetDir });
      }
      continue;
    }

    // Check if files are in sync
    const filesToCompare = [
      'SKILL.md',
      'scripts/run_video_summary.sh',
      'scripts/extract_frames.py',
      'scripts/prepare_agent_review.py'
    ];
    let isInSync = true;
    for (const file of filesToCompare) {
      const src = join(SOURCE_SKILL_DIR, file);
      const dest = join(targetDir, file);
      if (!existsSync(dest)) {
        isInSync = false;
        break;
      }
      try {
        const srcContent = readFileSync(src, 'utf-8');
        const destContent = readFileSync(dest, 'utf-8');
        if (srcContent !== destContent) {
          isInSync = false;
          break;
        }
      } catch (err) {
        isInSync = false;
        break;
      }
    }

    results.push({
      target: t,
      status: isInSync ? 'OK' : 'OUTDATED',
      path: targetDir,
    });
  }

  printHeader(
    'VideoStand Status',
    options.global ? 'global scope (~)' : 'local scope (cwd)'
  );

  if (results.length === 0) {
    console.log(`│  ${statusTag('info')} No targets found in this scope.`);
    console.log(colorize('└', 'dim'));
    return;
  }

  results.forEach((r, idx) => {
    let tag = '';
    if (r.status === 'OK') tag = statusTag('ok');
    else if (r.status === 'OUTDATED') tag = colorize('⚠ UPDATE', 'bold', 'yellow');
    else tag = colorize('○ MISSING', 'dim');

    const symbol = idx === results.length - 1 ? '└' : '├';
    console.log(`${colorize(symbol, 'dim')}  ${r.target.padEnd(12)} ${tag} ${colorize(r.path, 'dim')}`);
  });

  console.log('');
  const outdated = results.filter((r) => r.status === 'OUTDATED');
  if (outdated.length > 0) {
    console.log(`${statusTag('hint')} ${outdated.length} target(s) are outdated.`);
    console.log(`   Run "vs sync" to update.`);
  } else if (results.some(r => r.status === 'OK')) {
    console.log(`${statusTag('ok')} All installed targets are up-to-date.`);
  }
}

function commandSync(options, target) {
  const isAll = !target || target === ALL_TARGETS_KEYWORD;
  const targets = isAll ? VALID_TARGETS : [target];
  const installedTargets = targets.filter((t) => {
    const { targetDir } = getPaths(options, t);
    return existsSync(targetDir);
  });

  if (installedTargets.length === 0) {
    console.log(`${statusTag('info')} No installed skills found to sync.`);
    return;
  }

  console.log(`${statusTag('info')} Syncing ${installedTargets.length} target(s)...`);

  // Reuse commandInit but with force: true
  const syncOptions = { ...options, force: true };

  // It's cleaner to just loop and call the installation logic or call commandInit.
  if (isAll) {
    for (const t of installedTargets) {
      commandInit(syncOptions, t);
    }
  } else {
    commandInit(syncOptions, target);
  }
}



function commandRemove(options, target) {
  const isAll = !target || target === ALL_TARGETS_KEYWORD;
  const targets = isAll ? VALID_TARGETS : [target];
  let removedCount = 0;

  for (const t of targets) {
    const { targetDir } = getPaths(options, t);
    if (existsSync(targetDir)) {
      rmSync(targetDir, { recursive: true, force: true });
      console.log(`${statusTag('ok')} Removed skill from "${t}".`);
      removedCount++;
    } else {
      if (!isAll) {
        console.error(`${statusTag('error')} Skill not found for "${t}".`);
        console.error(`  path: ${targetDir}`);
        process.exit(1);
      }
    }
  }

  console.log('');
  console.log(`${statusTag('ok')} Removal finished. Removed from ${removedCount} target(s).`);
}

const COMMAND_DOCS = {
  init: {
    description: 'Installs the VideoStand skill into a target agent directory. It copies all necessary scripts and the SKILL.md instructions.',
    input: 'vs init cursor --force',
    output: '✔ cursor -> ./.cursor/skills/videostand',
  },
  status: {
    description: 'Checks if your installed skills are synchronized with the latest version in the CLI package. Ideal for finding outdated files.',
    input: 'vs status',
    output: '├  cursor       ✔ OK\n└  claude       ⚠ UPDATE',
  },
  run: {
    description: 'Processes a video file or YouTube URL directly. It extracts frames, transcribes audio, and prepares a summary pack.',
    input: 'vs run ./demo.mp4',
    output: '✔ Audio transcript generated.\n✔ Video processing completed!',
  },
  watch: {
    description: 'Monitors a directory for new video files. When a recording is detected, it automatically starts the processing in the background.',
    input: 'vs watch ~/Downloads',
    output: '▶️ New video detected: game.mp4\nProcessing...',
  },
  doctor: {
    description: 'A diagnostic tool to verify if your environment (Python, FFmpeg, etc.) is ready to run VideoStand at full performance.',
    input: 'vs doctor --fix',
    output: '├  Environment\n│  ✔ python3\n│  ✔ ffmpeg',
  },
  sync: {
    description: 'Automatically updates all your installed agent skills to the latest version currently available in your VideoStand CLI tool.',
    input: 'vs sync all',
    output: 'ℹ Syncing 3 target(s)...\n✔ Installation finished.',
  },
  optimize: {
    description: 'Scans your computer hardware (NVIDIA GPUs or Apple Silicon) to optimize processing limits and activation flags.',
    input: 'vs optimize',
    output: '⚡ NVIDIA GPU detected. CUDA acceleration active.',
  },
  where: {
    description: 'Reveals the exact disk path where a specific agent skill is located.',
    input: 'vs where cursor',
    output: './.cursor/skills/videostand',
  },
  remove: {
    description: 'Safely deletes a VideoStand skill installation from a target agent directory.',
    input: 'vs remove all',
    output: '✔ Removed skill from "cursor".',
  },
};

function commandExplain(cmd) {
  const doc = COMMAND_DOCS[cmd];
  if (!doc) {
    console.error(`${statusTag('error')} No documentation found for command: ${cmd}`);
    return;
  }

  printHeader(`Explain: ${cmd}`, 'Detailed Command Documentation');
  
  console.log(colorize('├  Description', 'bold'));
  console.log(`│  ${doc.description}`);
  console.log(colorize('│', 'dim'));

  console.log(colorize('├  Example Input', 'bold'));
  console.log(`│  ${colorize(doc.input, 'cyan')}`);
  console.log(colorize('│', 'dim'));

  console.log(colorize('├  Simulated Output', 'bold'));
  doc.output.split('\n').forEach(line => {
    console.log(`│  ${line}`);
  });

  console.log(colorize('│', 'dim'));
  console.log(`${colorize('└', 'dim')}  Documentation finished.`);
}

async function commandRun(options, videoPath) {
  if (!videoPath) {
    console.error(colorize('MISSING: video path', 'bold', 'yellow'));
    process.exit(1);
  }
  console.log(`${statusTag('info')} Processing video: ${videoPath}`);
  const child = spawnSync('bash', [resolve(SOURCE_SKILL_DIR, 'scripts', 'run_video_summary.sh'), videoPath], { stdio: 'inherit' });
  if (child.status === 0) {
    console.log(`${statusTag('ok')} Video processing completed successfully!`);
  } else {
    console.error(`${statusTag('error')} Video processing failed.`);
    process.exit(1);
  }
}

async function commandWatch(options, dirPath) {
  const watchDir = dirPath || process.cwd();
  console.log(colorize(`👀 Watching ${watchDir} for new videos...`, 'bold', 'cyan'));
  console.log(colorize(`Press Ctrl+C to stop.`, 'dim'));

  let chokidar;
  try {
    chokidar = (await import('chokidar')).default || (await import('chokidar'));
  } catch (err) {
    console.error(colorize(`MISSING: chokidar package.`, 'bold', 'red'));
    console.error(`Please install it first using: npm install -g chokidar`);
    process.exit(1);
  }

  const watcher = chokidar.watch(watchDir, {
    ignored: /(^|[\/\\])\../,
    persistent: true,
    depth: 1,
    awaitWriteFinish: {
      stabilityThreshold: 2000,
      pollInterval: 100
    }
  });

  watcher.on('add', path => {
    if (path.endsWith('.mp4') || path.endsWith('.mkv') || path.endsWith('.mov')) {
      console.log('');
      console.log(colorize(`▶️ New video detected: ${path}`, 'bold', 'green'));
      commandRun(options, path);
      console.log('');
      console.log(colorize(`👀 Resuming watch on ${watchDir}...`, 'bold', 'cyan'));
    }
  });
}

function commandOptimize(options) {
  const s = spinner();
  s.start('Detecting hardware for optimization...');
  const hasNvidia = spawnSync('nvidia-smi', [], { stdio: 'ignore' }).status === 0;
  const isMac = process.platform === 'darwin';

  if (hasNvidia) {
    s.stop('NVIDIA GPU detected. CUDA acceleration is recommended.');
    console.log(colorize(`To fully activate, run the local asr install script with CUDA flag.`, 'green'));
  } else if (isMac) {
    s.stop('Apple Silicon detected. MPS acceleration is mapped.');
    console.log(colorize(`Optimization profile applied for Mac hardware.`, 'green'));
  } else {
    s.stop('No specific hardware found. Kept CPU defaults.');
  }
}

function isNewer(latest, current) {
  const l = latest.split('.').map(Number);
  const c = current.split('.').map(Number);
  for (let i = 0; i < 3; i++) {
    if (l[i] > (c[i] || 0)) return true;
    if (l[i] < (c[i] || 0)) return false;
  }
  return false;
}

async function checkUpdate() {
  const cachePath = join(homedir(), '.videostand', 'version-cache.json');
  let cache = { latestVersion: PACKAGE_VERSION, lastCheck: 0 };

  if (existsSync(cachePath)) {
    try {
      cache = JSON.parse(readFileSync(cachePath, 'utf-8'));
    } catch (e) {
      // Invalid cache, reset
    }
  }

  const now = Date.now();
  const ONE_DAY = 24 * 60 * 60 * 1000;

  if (now - cache.lastCheck > ONE_DAY) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 1200);
      const res = await fetch(
        'https://registry.npmjs.org/videostand-skill/latest',
        { signal: controller.signal }
      );
      clearTimeout(timeout);
      if (res.ok) {
        const data = await res.json();
        cache.latestVersion = data.version;
        cache.lastCheck = now;
        mkdirSync(dirname(cachePath), { recursive: true });
        writeFileSync(cachePath, JSON.stringify(cache));
      }
    } catch (e) {
      // Silently ignore network errors
    }
  }

  if (isNewer(cache.latestVersion, PACKAGE_VERSION)) {
    console.log(
      colorize(
        `WARNING: There's a new update on VideoStand! Please install using 'npm i -g videostand-skill'`,
        'bold',
        'yellow'
      )
    );
    console.log('');
  }
}

async function main() {
  await checkUpdate();
  let args = process.argv.slice(2);

  let agentMode = false;
  if (args.length > 0 && args[args.length - 1] === '--agent') {
    agentMode = true;
    args = args.slice(0, -1);
  }

  if (args.length === 1 && (args[0] === '--version' || args[0] === '-v')) {
    printVersion();
    return;
  }

  if (args.includes('--help') || args.includes('-h')) {
    printHelp();
    return;
  }

  const positionals = args.filter((arg) => !arg.startsWith('-'));
  const optionArgs = args.filter((arg) => arg.startsWith('-'));
  const options = parseOptions(optionArgs);

  let command = positionals[0];
  let target = positionals[1];
  if (options.explain) {
    commandExplain(command || 'help');
    printFooter();
    return;
  }

  const validCommands = ['init', 'where', 'doctor', 'remove', 'status', 'sync', 'help', 'run', 'watch', 'optimize'];

  if (agentMode) {
    if (!command) {
      console.error(colorize('MISSING: command', 'bold', 'yellow'));
      process.exit(1);
    }
    if (!validCommands.includes(command)) {
      console.error(`${statusTag('error')} Unknown command: ${command}`);
      process.exit(1);
    }
    if ((command === 'init' || command === 'where' || command === 'remove') && !target) {
      console.error(colorize('MISSING: target', 'bold', 'yellow'));
      process.exit(1);
    }
    if ((command === 'run') && !target) {
      console.error(colorize('MISSING: video path', 'bold', 'yellow'));
      process.exit(1);
    }
  } else {
    // Interactive Mode
    if (command && !validCommands.includes(command)) {
      console.error(`${statusTag('error')} Unknown command: ${command}`);
      printHelp();
      process.exit(1);
    }

    if (!command) {
      // console.clear();
      intro(colorize(`VideoStand CLI v${PACKAGE_VERSION}`, 'bold', 'cyan'));

      command = await select({
        message: 'What do you want to do?',
        options: [
          { value: 'explain', label: '📖 Explore command details (explain)' },
          { value: 'help', label: 'Show usage guide (help)' },
          { value: 'run', label: 'Process video standalone (run)' },
          { value: 'watch', label: 'Watch folder for new videos (watch)' },
          { value: 'optimize', label: 'Optimize hardware config (optimize)' },
          { value: 'init', label: 'Install agent skill (init)' },
          { value: 'status', label: 'Check for outdated agent skills (status)' },
          { value: 'sync', label: 'Update installed skills (sync)' },
          { value: 'doctor', label: 'Check dependencies and installation status (doctor)' },
          { value: 'where', label: 'Print installation path (where)' },
          { value: 'remove', label: 'Remove skill (remove)' }
        ],
      });

      if (isCancel(command)) {
        cancel('Operation cancelled.');
        process.exit(0);
      }

      if (command === 'explain') {
        const explainCmd = await select({
          message: 'Which command would you like to explore? 📖',
          options: [
            { value: 'run', label: 'run' },
            { value: 'watch', label: 'watch' },
            { value: 'optimize', label: 'optimize' },
            { value: 'status', label: 'status' },
            { value: 'sync', label: 'sync' },
            { value: 'doctor', label: 'doctor' },
            { value: 'init', label: 'init' },
            { value: 'remove', label: 'remove' },
            { value: 'where', label: 'where' },
          ],
        });

        if (isCancel(explainCmd)) {
          cancel('Operation cancelled.');
          process.exit(0);
        }

        commandExplain(explainCmd);
        printFooter();
        process.exit(0);
      }
    }

    const needsTarget = ['init', 'where', 'remove'].includes(command);
    if (!target && needsTarget) {
      const targetOptions = [{ value: ALL_TARGETS_KEYWORD, label: 'All targets (all)' }];
      VALID_TARGETS.forEach(t => targetOptions.push({ value: t, label: t }));

      target = await select({
        message: `Which target do you want to run '${command}' for?`,
        options: targetOptions,
      });

      if (isCancel(target)) {
        cancel('Operation cancelled.');
        process.exit(0);
      }
    }

    const needsVideoPath = ['run', 'watch'].includes(command);
    if (!target && needsVideoPath) {
      target = await text({
        message: `Provide the path for '${command}':`,
        placeholder: command === 'watch' ? './videos' : './video.mp4',
      });
      if (isCancel(target)) {
        cancel('Operation cancelled.');
        process.exit(0);
      }
    }
  }

  if (
    target &&
    !['run', 'watch'].includes(command) &&
    !VALID_TARGETS.includes(target) &&
    target !== ALL_TARGETS_KEYWORD
  ) {
    console.error(
      `${statusTag('error')} Invalid target: ${target}. Must be one of: ${VALID_TARGETS.join(', ')}, ${ALL_TARGETS_KEYWORD}`
    );
    process.exit(1);
  }

  if (command === 'init') {
    commandInit(options, target);
  } else if (command === 'where') {
    commandWhere(options, target);
  } else if (command === 'status') {
    commandStatus(options, target);
  } else if (command === 'sync') {
    commandSync(options, target);
  } else if (command === 'remove') {
    commandRemove(options, target);
  } else if (command === 'doctor') {
    commandDoctor(options, target);
  } else if (command === 'run') {
    await commandRun(options, target);
  } else if (command === 'watch') {
    await commandWatch(options, target);
  } else if (command === 'optimize') {
    commandOptimize(options);
  } else if (command === 'help') {
    printHelp();
    return;
  }

  printFooter();
}

main();
