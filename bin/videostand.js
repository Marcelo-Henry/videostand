#!/usr/bin/env node

import { cpSync, existsSync, mkdirSync, readFileSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { homedir } from 'node:os';
import { spawnSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const SOURCE_SKILL_DIR = resolve(__dirname, '..', 'assets', 'skills', 'videostand');
const PACKAGE_JSON_PATH = resolve(__dirname, '..', 'package.json');
const PACKAGE_VERSION = JSON.parse(readFileSync(PACKAGE_JSON_PATH, 'utf-8')).version;

const TARGETS = {
  codex: '.codex',
  kiro: '.kiro',
  claude: '.claude',
};

const VALID_TARGETS = Object.keys(TARGETS);
const ALL_TARGETS_KEYWORD = 'all';

function printHelp() {
  console.log('VideoStand CLI');
  console.log('');
  console.log('Alias:');
  console.log('  vs  Same as videostand');
  console.log('');
  console.log('Usage:');
  console.log('  videostand init <codex|kiro|claude|all> [--force]');
  console.log('  videostand -g init <codex|kiro|claude|all> [--force]');
  console.log('  videostand where <codex|kiro|claude|all>');
  console.log('  videostand -g where <codex|kiro|claude|all>');
  console.log('  videostand doctor [codex|kiro|claude|all] [--strict] [--json]');
  console.log('  videostand -g doctor [codex|kiro|claude|all] [--strict] [--json]');
  console.log('  videostand --version');
  console.log('  videostand -v');
  console.log('  videostand --help');
  console.log('');
  console.log('Commands:');
  console.log('  init   Install skill folder for the given target');
  console.log('  where  Print installation path for the given target');
  console.log('  doctor Check environment dependencies and skill installation');
  console.log('');
  console.log('Targets:');
  console.log('  codex   Use .codex directory');
  console.log('  kiro    Use .kiro directory');
  console.log('  claude  Use .claude directory');
  console.log('  all     Apply command to all targets');
  console.log('');
  console.log('Options:');
  console.log('  -g, --global  Use ~/.<target> instead of ./.<target>');
  console.log('  --force       Overwrite existing skill folder');
  console.log('  --strict      For doctor: exit 1 if required dependencies are missing');
  console.log('  --json        For doctor: output machine-readable JSON');
}

function printVersion() {
  console.log(PACKAGE_VERSION);
}

function parseOptions(args) {
  const options = {
    force: false,
    global: false,
    strict: false,
    json: false,
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

    if (arg === '--strict') {
      options.strict = true;
      continue;
    }

    if (arg === '--json') {
      options.json = true;
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

    console.error(`Unknown option: ${arg}`);
    process.exit(1);
  }

  return options;
}

function getPaths(options, target) {
  const dotDir = TARGETS[target];
  const baseDir = options.global ? homedir() : process.cwd();
  const targetRoot = join(resolve(baseDir), dotDir);
  const targetDir = join(targetRoot, 'skills', 'videostand');

  return { targetRoot, targetDir };
}

function commandWhere(options, target) {
  const targets = target === ALL_TARGETS_KEYWORD ? VALID_TARGETS : [target];
  for (const t of targets) {
    const { targetDir } = getPaths(options, t);
    if (target === ALL_TARGETS_KEYWORD) {
      console.log(`${t}: ${targetDir}`);
    } else {
      console.log(targetDir);
    }
  }
}

function commandInit(options, target) {
  if (!existsSync(SOURCE_SKILL_DIR)) {
    console.error('Skill source not found in package assets.');
    process.exit(1);
  }

  const targets = target === ALL_TARGETS_KEYWORD ? VALID_TARGETS : [target];
  for (const t of targets) {
    const { targetDir } = getPaths(options, t);

    if (existsSync(targetDir)) {
      if (!options.force) {
        console.error(`Skill already exists at: ${targetDir}`);
        console.error('Run again with --force to overwrite.');
        process.exit(1);
      }
      rmSync(targetDir, { recursive: true, force: true });
    }

    mkdirSync(dirname(targetDir), { recursive: true });
    cpSync(SOURCE_SKILL_DIR, targetDir, { recursive: true });

    const label = t.charAt(0).toUpperCase() + t.slice(1);
    console.log(`VideoStand skill installed successfully for ${label}.`);
    console.log(`Path: ${targetDir}`);
  }
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
  const targets =
    !target || target === ALL_TARGETS_KEYWORD ? VALID_TARGETS : [target];
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

  console.log('VideoStand Doctor');
  console.log('');
  console.log('Environment checks:');

  for (const [cmd, ok] of Object.entries(envChecks.required)) {
    console.log(`  ${ok ? '[ok]  ' : '[miss]'} ${cmd}`);
  }

  for (const [cmd, ok] of Object.entries(envChecks.optional)) {
    console.log(
      `  ${ok ? '[ok]  ' : '[warn]'} ${cmd} (optional, required only for YouTube input)`
    );
  }

  if (envChecks.fasterWhisper) {
    console.log('  [ok]   faster-whisper Python package');
  } else {
    console.log('  [warn] faster-whisper Python package (optional for visual-only summary)');
  }

  for (const t of targets) {
    const info = installChecks[t];
    console.log('');
    console.log(`Installed skill check (${t}${options.global ? ' global' : ' local'}):`);
    console.log(
      `  ${info.skillFile ? '[ok]  ' : '[miss]'} ${join(info.path, 'SKILL.md')}`
    );
    console.log(
      `  ${info.runScript ? '[ok]  ' : '[miss]'} ${join(info.path, 'scripts', 'run_video_summary.sh')}`
    );
  }

  console.log('');
  if (envChecks.missingRequired.length === 0) {
    console.log('[ok] Doctor finished. Required dependencies are present.');
    return;
  }

  console.log(
    `[warn] Missing required dependencies: ${envChecks.missingRequired.join(', ')}`
  );
  console.log('[hint] Install ffmpeg and python3 to run full local pipeline.');
  if (options.strict) {
    process.exit(1);
  }
}

function main() {
  const args = process.argv.slice(2);

  if (args.length === 1 && (args[0] === '--version' || args[0] === '-v')) {
    printVersion();
    return;
  }

  if (args.length === 0 || args.includes('--help') || args.includes('-h')) {
    printHelp();
    return;
  }

  const positionals = args.filter((arg) => !arg.startsWith('-'));

  if (positionals.length === 0) {
    printHelp();
    process.exit(1);
  }

  const command = positionals[0];
  const target = positionals[1];

  if (command !== 'init' && command !== 'where' && command !== 'doctor') {
    console.error(`Unknown command: ${command}`);
    printHelp();
    process.exit(1);
  }

  if ((command === 'init' || command === 'where') && !target) {
    console.error(`Missing target. Usage: videostand ${command} <codex|kiro|claude|all>`);
    process.exit(1);
  }

  if (
    target &&
    !VALID_TARGETS.includes(target) &&
    target !== ALL_TARGETS_KEYWORD
  ) {
    console.error(
      `Invalid target: ${target}. Must be one of: ${VALID_TARGETS.join(', ')}, ${ALL_TARGETS_KEYWORD}`
    );
    process.exit(1);
  }

  const optionArgs = args.filter((arg) => arg !== command && arg !== target);
  const options = parseOptions(optionArgs);

  if (command === 'init') {
    commandInit(options, target);
    return;
  }

  if (command === 'where') {
    commandWhere(options, target);
    return;
  }

  if (command === 'doctor') {
    commandDoctor(options, target);
    return;
  }
}

main();
