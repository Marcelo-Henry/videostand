#!/usr/bin/env bash
set -euo pipefail

log_info() {
  echo "[info] $*"
}

log_error() {
  echo "[error] $*" >&2
}

have_ffmpeg_tools() {
  command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1
}

require_sudo_auth() {
  if ! command -v sudo >/dev/null 2>&1; then
    log_error "sudo nao esta disponivel neste sistema."
    return 1
  fi
  log_info "Sera solicitada autenticacao de administrador."
  sudo -v
}

install_linux() {
  if command -v apt-get >/dev/null 2>&1; then
    require_sudo_auth || return 1
    sudo apt-get update -y
    sudo apt-get install -y ffmpeg
    return 0
  fi
  if command -v dnf >/dev/null 2>&1; then
    require_sudo_auth || return 1
    sudo dnf install -y ffmpeg
    return 0
  fi
  if command -v yum >/dev/null 2>&1; then
    require_sudo_auth || return 1
    sudo yum install -y ffmpeg
    return 0
  fi
  if command -v pacman >/dev/null 2>&1; then
    require_sudo_auth || return 1
    sudo pacman -Sy --noconfirm ffmpeg
    return 0
  fi
  if command -v zypper >/dev/null 2>&1; then
    require_sudo_auth || return 1
    sudo zypper --non-interactive install ffmpeg
    return 0
  fi
  log_error "Nao foi encontrado gerenciador de pacotes suportado para Linux."
  return 1
}

install_macos() {
  if command -v brew >/dev/null 2>&1; then
    if command -v sudo >/dev/null 2>&1; then
      log_info "O sistema pode solicitar senha de administrador."
      sudo -v || true
    fi
    brew install ffmpeg
    return 0
  fi
  if command -v port >/dev/null 2>&1; then
    require_sudo_auth || return 1
    sudo port selfupdate
    sudo port install ffmpeg
    return 0
  fi
  log_error "Nem Homebrew nem MacPorts foram encontrados no macOS."
  return 1
}

install_windows() {
  if command -v powershell.exe >/dev/null 2>&1; then
    log_info "Uma janela de permissao do Windows deve aparecer para aprovacao de administrador."
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command \
      '$cmd = "winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements"; Start-Process powershell -Verb RunAs -Wait -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-Command",$cmd)'
    return 0
  fi
  if command -v winget >/dev/null 2>&1; then
    winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
    return 0
  fi
  log_error "Nao foi possivel acionar instalacao automatica no Windows."
  return 1
}

main() {
  if have_ffmpeg_tools; then
    log_info "ffmpeg ja esta instalado."
    return 0
  fi

  case "$(uname -s)" in
    Linux)
      install_linux || return 1
      ;;
    Darwin)
      install_macos || return 1
      ;;
    MINGW*|MSYS*|CYGWIN*|Windows_NT)
      install_windows || return 1
      ;;
    *)
      log_error "Sistema operacional nao suportado para instalacao automatica."
      return 1
      ;;
  esac

  if have_ffmpeg_tools; then
    log_info "ffmpeg instalado com sucesso."
    return 0
  fi

  log_error "Instalacao executada, mas ffmpeg/ffprobe ainda nao estao no PATH."
  return 1
}

main "$@"
