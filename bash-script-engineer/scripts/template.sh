#!/usr/bin/env bash
#
# <SCRIPT_NAME> - <one-line description>
#
# Usage:
#   ./<script_name>.sh [OPTIONS]
#
# This template is the standard starting point for every bash script written
# with the bash-script-engineer skill. It already wires up config-file
# overloading, colored logging, --dry-run, --verbose, --help, --backup, and
# both an interactive mode and a flag-driven mode. Copy this file, rename it,
# and fill in the TODO sections. Delete any block you genuinely don't need
# (e.g. the backup helpers if the script never touches files), but keep the
# rest intact so every script in a project behaves the same way.

set -euo pipefail
IFS=$'\n\t'

# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------
readonly SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
readonly SCRIPT_VERSION="1.0.0"

# ---------------------------------------------------------------------------
# Colors
#
# Colors are opt-out, not opt-in: they make script output far easier to scan
# (errors jump out in red, successes in green). But they must never break a
# script that is piped, redirected to a file, or run with NO_COLOR set, so
# they are disabled automatically whenever stdout isn't an interactive
# terminal, and can always be disabled explicitly with --no-color.
# ---------------------------------------------------------------------------
setup_colors() {
    if [[ -t 1 ]] && [[ -z "${NO_COLOR:-}" ]] && [[ "${USE_COLOR:-true}" == "true" ]]; then
        COLOR_RED=$'\033[0;31m'
        COLOR_GREEN=$'\033[0;32m'
        COLOR_YELLOW=$'\033[0;33m'
        COLOR_BLUE=$'\033[0;34m'
        COLOR_CYAN=$'\033[0;36m'
        COLOR_BOLD=$'\033[1m'
        COLOR_RESET=$'\033[0m'
    else
        COLOR_RED=""; COLOR_GREEN=""; COLOR_YELLOW=""; COLOR_BLUE=""
        COLOR_CYAN=""; COLOR_BOLD=""; COLOR_RESET=""
    fi
}

# ---------------------------------------------------------------------------
# Logging
#
# Everything user-facing goes through these functions instead of raw echo,
# so that verbosity and color stay consistent everywhere in the script.
# Info/warn/error go to stderr so stdout stays clean for any real script
# output that a caller might want to pipe or capture.
# ---------------------------------------------------------------------------
log_debug() {
    [[ "${VERBOSE:-false}" == "true" ]] || return 0
    printf '%s[DEBUG]%s %s\n' "${COLOR_CYAN}" "${COLOR_RESET}" "$*" >&2
}

log_info() {
    printf '%s[INFO]%s %s\n' "${COLOR_BLUE}" "${COLOR_RESET}" "$*" >&2
}

log_success() {
    printf '%s[ OK ]%s %s\n' "${COLOR_GREEN}" "${COLOR_RESET}" "$*" >&2
}

log_warn() {
    printf '%s[WARN]%s %s\n' "${COLOR_YELLOW}" "${COLOR_RESET}" "$*" >&2
}

log_error() {
    printf '%s[FAIL]%s %s\n' "${COLOR_RED}" "${COLOR_RESET}" "$*" >&2
}

die() {
    log_error "$*"
    exit 1
}

# ---------------------------------------------------------------------------
# Cleanup / error trap
#
# A single trap keeps ad-hoc temp files from leaking and reports the exact
# line a failure happened on, which saves a lot of debugging time versus a
# bare "something failed" message.
# ---------------------------------------------------------------------------
TMP_FILES=()

cleanup() {
    local exit_code=$?
    for f in "${TMP_FILES[@]:-}"; do
        [[ -n "$f" && -e "$f" ]] && rm -rf -- "$f"
    done
    exit "$exit_code"
}
trap cleanup EXIT

on_error() {
    local line=$1
    log_error "Unexpected error near line ${line}. Aborting."
}
trap 'on_error $LINENO' ERR

# ---------------------------------------------------------------------------
# Defaults
#
# Every overridable setting gets a default here first. This is layer 1 of 3:
# defaults -> config file -> CLI flags, each layer overriding the previous
# one. Keeping defaults in one block makes it obvious what can be tuned.
# ---------------------------------------------------------------------------
CONFIG_FILE=".env"
DRY_RUN=false
VERBOSE=false
BACKUP=false
INTERACTIVE=false
USE_COLOR=true

# TODO: add script-specific defaults here, e.g.:
# TARGET_DIR="./data"
# RETENTION_DAYS=7

# ---------------------------------------------------------------------------
# Config file loading (layer 2)
#
# The config file only ever supplies KEY=VALUE pairs for variables that
# already have a default above; it must never be able to inject arbitrary
# code. That's why this parses line by line instead of `source`-ing the
# file. Lines starting with # and blank lines are skipped. Values may be
# quoted or unquoted.
# ---------------------------------------------------------------------------
load_config_file() {
    local file="$1"
    [[ -f "$file" ]] || { log_debug "No config file at '${file}', using defaults/CLI only."; return 0; }

    log_debug "Loading config from '${file}'"
    local line key value
    while IFS='=' read -r key value || [[ -n "$key" ]]; do
        key="${key%%[[:space:]]*}"
        [[ -z "$key" || "$key" == \#* ]] && continue
        value="${value%\"}"; value="${value#\"}"
        value="${value%\'}"; value="${value#\'}"
        # Only ever assign to variables that already exist as a default,
        # so an unexpected key in the file can't create surprise state.
        if declare -p "$key" &>/dev/null; then
            printf -v "$key" '%s' "$value"
            log_debug "  ${key}=${value}"
        else
            log_warn "Ignoring unknown config key '${key}' in ${file}"
        fi
    done < "$file"
}

# ---------------------------------------------------------------------------
# Usage / help
# ---------------------------------------------------------------------------
usage() {
    cat <<EOF
${COLOR_BOLD}${SCRIPT_NAME}${COLOR_RESET} v${SCRIPT_VERSION}
<one-line description>

${COLOR_BOLD}USAGE${COLOR_RESET}
    ${SCRIPT_NAME} [OPTIONS]

${COLOR_BOLD}OPTIONS${COLOR_RESET}
    -c, --config FILE     Config file to load (default: ${CONFIG_FILE})
    -i, --interactive     Prompt for values instead of reading flags/config
    -b, --backup          Back up any file before modifying it
    -n, --dry-run         Show what would happen without changing anything
    -v, --verbose         Print debug/diagnostic output
        --no-color        Disable colored output
    -h, --help            Show this help and exit
        --version         Show version and exit

${COLOR_BOLD}CONFIG FILE${COLOR_RESET}
    Any option above can also be set via the config file (default: .env),
    using KEY=VALUE pairs, e.g.:
        DRY_RUN=true
        BACKUP=true
    Precedence, lowest to highest: built-in defaults < config file < CLI flags.

${COLOR_BOLD}EXAMPLES${COLOR_RESET}
    ${SCRIPT_NAME} --dry-run --verbose
    ${SCRIPT_NAME} --config prod.env --backup
    ${SCRIPT_NAME} --interactive
EOF
}

# ---------------------------------------------------------------------------
# CLI argument parsing (layer 3, highest precedence)
#
# A plain `while`/`case` loop is used instead of getopts so that long
# options (--dry-run) work as naturally as short ones (-n); getopts alone
# only handles short options cleanly.
# ---------------------------------------------------------------------------
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -c|--config)
                CONFIG_FILE="$2"; shift 2 ;;
            -i|--interactive)
                INTERACTIVE=true; shift ;;
            -b|--backup)
                BACKUP=true; shift ;;
            -n|--dry-run)
                DRY_RUN=true; shift ;;
            -v|--verbose)
                VERBOSE=true; shift ;;
            --no-color)
                USE_COLOR=false; shift ;;
            -h|--help)
                usage; exit 0 ;;
            --version)
                printf '%s\n' "${SCRIPT_VERSION}"; exit 0 ;;
            --)
                shift; break ;;
            -*)
                die "Unknown option: $1 (see --help)" ;;
            *)
                # TODO: handle positional arguments here if the script needs any
                break ;;
        esac
    done
}

# ---------------------------------------------------------------------------
# Interactive mode
#
# Triggered with -i/--interactive, or automatically when the script is run
# with no arguments at all in a real terminal — this keeps the script usable
# for someone who just double-clicks/runs it without knowing the flags.
# ---------------------------------------------------------------------------
prompt_yn() {
    local prompt="$1" default="${2:-n}" reply
    local hint="y/N"; [[ "$default" == "y" ]] && hint="Y/n"
    read -r -p "$(printf '%s%s%s [%s]: ' "${COLOR_YELLOW}" "$prompt" "${COLOR_RESET}" "$hint")" reply
    reply="${reply:-$default}"
    [[ "$reply" =~ ^[Yy] ]]
}

run_interactive() {
    log_info "Interactive mode — press Enter to accept the default shown in [brackets]."
    prompt_yn "Enable dry-run (no changes made)?" "$([[ "$DRY_RUN" == true ]] && echo y || echo n)" && DRY_RUN=true || DRY_RUN=false
    prompt_yn "Back up files before modifying them?" "$([[ "$BACKUP" == true ]] && echo y || echo n)" && BACKUP=true || BACKUP=false
    prompt_yn "Verbose output?" "$([[ "$VERBOSE" == true ]] && echo y || echo n)" && VERBOSE=true || VERBOSE=false
    # TODO: prompt for script-specific values here, e.g.:
    # read -r -p "Target directory [${TARGET_DIR}]: " input
    # TARGET_DIR="${input:-$TARGET_DIR}"
}

# ---------------------------------------------------------------------------
# Dry-run command wrapper
#
# Route every state-changing command through this instead of calling it
# directly, so --dry-run reliably shows exactly what would run without any
# risk of a stray command slipping through unguarded.
# ---------------------------------------------------------------------------
run_cmd() {
    if [[ "$DRY_RUN" == true ]]; then
        printf '%s[DRYRUN]%s would run: %s\n' "${COLOR_YELLOW}" "${COLOR_RESET}" "$*" >&2
    else
        log_debug "Running: $*"
        "$@"
    fi
}

# ---------------------------------------------------------------------------
# Backup helper
#
# Copies <file> into a "backups" directory next to it (created if missing)
# with a timestamped name, so a modification can always be undone. Timestamp
# format is DDMMYYYY-HH-MM, e.g. 05092026-14-32. Respects --dry-run.
# ---------------------------------------------------------------------------
backup_file() {
    local file="$1"
    [[ "$BACKUP" == true ]] || return 0
    [[ -f "$file" ]] || { log_warn "backup_file: '${file}' does not exist, skipping backup."; return 0; }

    local dir backups_dir timestamp dest
    dir="$(cd -- "$(dirname -- "$file")" &>/dev/null && pwd)"
    backups_dir="${dir}/backups"
    timestamp="$(date +%d%m%Y-%H-%M)"
    dest="${backups_dir}/$(basename -- "$file").${timestamp}.bak"

    if [[ "$DRY_RUN" == true ]]; then
        printf '%s[DRYRUN]%s would back up %s -> %s\n' "${COLOR_YELLOW}" "${COLOR_RESET}" "$file" "$dest" >&2
        return 0
    fi

    mkdir -p -- "$backups_dir"
    cp -p -- "$file" "$dest"
    log_success "Backed up $(basename -- "$file") -> backups/$(basename -- "$dest")"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    setup_colors
    parse_args "$@"

    # Config file is loaded after CLI parsing so --config is known, but its
    # values only fill in what CLI flags didn't already set explicitly.
    # Simplest robust approach: load config first with defaults, then
    # re-apply any flags the user actually passed. See conventions in
    # SKILL.md if this script needs stricter per-flag precedence tracking.
    load_config_file "$CONFIG_FILE"
    parse_args "$@"

    setup_colors  # re-run in case --no-color/config changed USE_COLOR

    [[ "$INTERACTIVE" == true ]] && run_interactive

    log_debug "CONFIG_FILE=${CONFIG_FILE} DRY_RUN=${DRY_RUN} VERBOSE=${VERBOSE} BACKUP=${BACKUP}"

    # TODO: script logic goes here. Example pattern for a file-modifying step:
    #
    # target="/path/to/file.conf"
    # backup_file "$target"
    # run_cmd sed -i 's/foo/bar/' "$target"

    log_success "Done."
}

main "$@"
