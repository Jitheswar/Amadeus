# An upgrade, or a run of amadeus-setup-git, can have set the identity already.
if [[ -z $(git config --global user.name) || -z $(git config --global user.email) ]]; then
  amadeus-notification-send -u critical -g  "$(amadeus-i18n firstRun.gitTitle)" "$(amadeus-i18n firstRun.gitBody)" \
    --exec amadeus-launch-floating-terminal-with-presentation amadeus-setup-git
fi
