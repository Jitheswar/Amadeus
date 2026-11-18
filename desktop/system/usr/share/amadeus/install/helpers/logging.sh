amadeus_log_to_stdout() {
  [[ ${AMADEUS_LOG_TO_STDOUT:-} == "1" || -z ${AMADEUS_INSTALL_LOG_FILE:-} ]]
}

amadeus_log_line() {
  if amadeus_log_to_stdout; then
    echo "$1"
  else
    echo "$1" >>"$AMADEUS_INSTALL_LOG_FILE"
  fi
}

start_install_log() {
  if ! amadeus_log_to_stdout; then
    mkdir -p "$(dirname "$AMADEUS_INSTALL_LOG_FILE")"
    touch "$AMADEUS_INSTALL_LOG_FILE"
    chmod 666 "$AMADEUS_INSTALL_LOG_FILE" 2>/dev/null || true
  fi

  export AMADEUS_START_TIME="${AMADEUS_START_TIME:-$(date '+%Y-%m-%d %H:%M:%S')}"
  export AMADEUS_START_EPOCH="${AMADEUS_START_EPOCH:-$(date +%s)}"

  amadeus_log_line "=== Amadeus Setup Started: $AMADEUS_START_TIME ==="
}

stop_install_log() {
  local end_time end_epoch duration mins secs
  end_time=$(date '+%Y-%m-%d %H:%M:%S')
  end_epoch=$(date +%s)

  amadeus_log_line "=== Amadeus Setup Completed: $end_time ==="

  if [[ -n ${AMADEUS_START_EPOCH:-} ]]; then
    duration=$((end_epoch - AMADEUS_START_EPOCH))
    mins=$((duration / 60))
    secs=$((duration % 60))
    amadeus_log_line "Amadeus setup: ${mins}m ${secs}s"
  fi
}

run_logged() {
  local script="$1"
  local exit_code errexit_was_set=0

  amadeus_log_line "[$(date '+%Y-%m-%d %H:%M:%S')] Starting: $script"

  case $- in
    *e*)
      errexit_was_set=1
      set +e
      ;;
  esac

  local runner=(bash -eE)
  if [[ ${AMADEUS_INSTALL_DEBUG:-} == "1" ]]; then
    runner=(bash -x -eE)
  fi

  if amadeus_log_to_stdout; then
    PS4='+ ${BASH_SOURCE[0]##*/}:${LINENO}:${FUNCNAME[0]:-main}: ' \
      "${runner[@]}" -c 'source "$1"' bash "$script" </dev/null 2>&1
  else
    PS4='+ ${BASH_SOURCE[0]##*/}:${LINENO}:${FUNCNAME[0]:-main}: ' \
      "${runner[@]}" -c 'source "$1"' bash "$script" </dev/null >>"$AMADEUS_INSTALL_LOG_FILE" 2>&1
  fi

  exit_code=$?
  (( errexit_was_set )) && set -e

  if (( exit_code == 0 )); then
    amadeus_log_line "[$(date '+%Y-%m-%d %H:%M:%S')] Completed: $script"
  else
    amadeus_log_line "[$(date '+%Y-%m-%d %H:%M:%S')] Failed: $script (exit code: $exit_code)"
  fi

  return $exit_code
}
