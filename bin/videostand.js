#!/usr/bin/env node

import { cpSync, existsSync, mkdirSync, readFileSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { homedir } from 'node:os';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const SOURCE_SKILL_DIR = resolve(__dirname, '..', 'assets', 'skills', 'videostand');
const PACKAGE_JSON_PATH = resolve(__dirname, '..', 'package.json');
const PACKAGE_VERSION = JSON.parse(readFileSync(PACKAGE_JSON_PATH, 'utf-8')).version;

const TARGETS = {
  codex: '.codex',
  kiro: '.kiro',
};

const VALID_TARGETS = Object.keys(TARGETS);

function printHelp() {
  console.log('VideoStand CLI');
  console.log('');
  console.log('Usage:');
  console.log('  videostand init <codex|kiro> [--force]');
  console.log('  videostand -g init <codex|kiro> [--force]');
  console.log('  videostand where <codex|kiro>');
  console.log('  videostand -g where <codex|kiro>');
  console.log('  videostand --version');
  console.log('  videostand -v');
  console.log('  videostand --help');
  console.log('');
  console.log('Commands:');
  console.log('  init   Install skill folder for the given target');
  console.log('  where  Print installation path for the given target');
  console.log('');
  console.log('Targets:');
  console.log('  codex  Use .codex directory');
  console.log('  kiro   Use .kiro directory');
  console.log('');
  console.log('Options:');
  console.log('  -g, --global  Use ~/.<target> instead of ./.<target>');
  console.log('  --force       Overwrite existing skill folder');
}

function printVersion() {
  console.log(PACKAGE_VERSION);
}

function parseOptions(args) {
  const options = {
    force: false,
    global: false,
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
  const { targetDir } = getPaths(options, target);
  console.log(targetDir);
}

function commandInit(options, target) {
  if (!existsSync(SOURCE_SKILL_DIR)) {
    console.error('Skill source not found in package assets.');
    process.exit(1);
  }

  const { targetDir } = getPaths(options, target);

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

  const label = target.charAt(0).toUpperCase() + target.slice(1);
  console.log(`VideoStand skill installed successfully for ${label}.`);
  console.log(`Path: ${targetDir}`);
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

  if (command !== 'init' && command !== 'where') {
    console.error(`Unknown command: ${command}`);
    printHelp();
    process.exit(1);
  }

  if (!target) {
    console.error(`Missing target. Usage: videostand ${command} <codex|kiro>`);
    process.exit(1);
  }

  if (!VALID_TARGETS.includes(target)) {
    console.error(`Invalid target: ${target}. Must be one of: ${VALID_TARGETS.join(', ')}`);
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
}

main();
