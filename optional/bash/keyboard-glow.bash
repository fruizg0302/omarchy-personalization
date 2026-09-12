# Per-machine completion feedback. Keep command text out of the lighting service.
[[ $- == *i* && -z ${_KEYBOARD_GLOW_SHELL_LOADED:-} ]] || return 0
_KEYBOARD_GLOW_SHELL_LOADED=1

# PS0 runs just before each interactive command. A timestamp in the runtime
# directory survives its subshell; no DEBUG trap or prompt framework is replaced.
PS0+='$(if [[ -d ${XDG_RUNTIME_DIR:-}/keyboard-glow ]]; then (umask 077; printf "%s" "$EPOCHSECONDS" > "$XDG_RUNTIME_DIR/keyboard-glow/shell-$$") 2>/dev/null; fi)'

_keyboard_glow_complete() {
  local rc=$? started elapsed minimum=${KEYBOARD_GLOW_MIN_SECONDS:-10} marker="${XDG_RUNTIME_DIR:-}/keyboard-glow/shell-$$"
  [[ $minimum =~ ^[0-9]+$ ]] || minimum=10
  if [[ -r $marker ]]; then
    IFS= read -r started < "$marker" || :
    : > "$marker"
    if [[ $started =~ ^[0-9]+$ ]]; then
      elapsed=$((EPOCHSECONDS - started))
      if (( elapsed >= minimum )) && (( rc != 130 && rc != 143 )); then
        local kind=success
        (( rc == 0 )) || kind=failure
        "$HOME/.local/bin/glow" alert "$kind" --quiet --no-wait >/dev/null 2>&1 || :
      fi
    fi
  fi
  return "$rc"
}
if [[ ${PROMPT_COMMAND@a} == *a* ]]; then
  PROMPT_COMMAND=(_keyboard_glow_complete "${PROMPT_COMMAND[@]}")
else
  PROMPT_COMMAND="_keyboard_glow_complete${PROMPT_COMMAND:+$'\n'$PROMPT_COMMAND}"
fi

# A one-shot Ollama run signals even if it completes in under ten seconds.
# An interactive chat signals when the chat command exits.
ollama() {
  if [[ ${1:-} == run ]]; then
    "$HOME/.local/bin/glow" run -- /usr/bin/ollama "$@"
  else
    command /usr/bin/ollama "$@"
  fi
}
