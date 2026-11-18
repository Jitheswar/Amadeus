# A language the install media preset (/etc/amadeus/language) becomes this
# user's desktop language; the system step generated its locale.
code=
[[ -r /etc/amadeus/language ]] && read -r code </etc/amadeus/language
if [[ -n $code ]]; then
  "$AMADEUS_PATH/bin/amadeus-language" seed "$code" || echo "Could not set the preset language $code" >&2
fi
