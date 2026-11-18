# Install media can preset the desktop language for its users. The marker is a
# registry code, read as data; the system locale stays English, because the
# console cannot draw every script, and the language applies per user.
marker=${AMADEUS_LANGUAGE_MARKER:-/etc/amadeus/language}
code=
[[ -r $marker ]] && read -r code <"$marker"
if [[ -n $code ]]; then
  if [[ $code =~ ^[a-z]{2,3}(-[A-Z]{2})?$ ]]; then
    "$AMADEUS_PATH/bin/amadeus-locale-generate" "$code"
  else
    echo "Ignoring an invalid language in $marker: $code" >&2
  fi
fi
