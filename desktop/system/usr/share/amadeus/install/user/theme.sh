# Setup user theme folder and seed the default only when no theme exists yet.
mkdir -p ~/.config/amadeus/themes

if [[ ! -s $HOME/.local/state/amadeus/current/theme.name ]]; then
  # iso-chroot and provision-owner both run without a live session to notify.
  if [[ ${AMADEUS_SETUP_CONTEXT:-runtime} != "runtime" ]]; then
    AMADEUS_THEME_HEADLESS=1 amadeus-theme-set "Tokyo Night"
    rm -f ~/.config/google-chrome/SingletonLock ~/.config/chromium/SingletonLock # otherwise archiso owns the browser singleton
  else
    amadeus-theme-set "Tokyo Night"
  fi
fi
amadeus-theme-set-pi --activate
amadeus-theme-set-fcitx5 --activate
# A headless theme set skips the retints, so the seeded config would keep its
# default icon theme until the first switch.
amadeus-theme-set-qt

mkdir -p ~/.config/btop/themes
ln -snf "$HOME/.local/state/amadeus/current/theme/btop.theme" ~/.config/btop/themes/current.theme
