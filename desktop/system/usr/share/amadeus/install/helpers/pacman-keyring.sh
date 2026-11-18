# This machine's pacman keyring, made in the background during a first install.
# Sourced by install/config/pacman-keyring.sh and install/post-install/pacman.sh;
# no shebang.
#
# Making the keyring takes seconds: pacman-key generates a master key, then
# imports, signs and disables keys and rebuilds the trust database. Nothing in
# system setup needs it until post-install/pacman.sh switches pacman to its real
# repositories, so config/pacman-keyring.sh starts it first thing, in a
# directory of its own while setup keeps using the keyring the image has, and
# post-install/pacman.sh waits for it and moves it into place. A run that never
# started or didn't finish leaves that step to make the keyring itself, as it
# always did.
#
# Only a first install starts one: the keyring it replaces holds nothing yet,
# where an upgrade's may hold keys the user added.
#
# Root always uses the real /etc. Only a non-root test may move it under
# AMADEUS_IMAGE_ROOT, as install/helpers/image-target.sh does.

amadeus_pacman_keyring_init() {
  local root=""
  (( EUID == 0 )) || root=${AMADEUS_IMAGE_ROOT:-}
  amadeus_pacman_keyring=$root/etc/pacman.d/gnupg
  amadeus_pacman_keyring_next=$root/etc/pacman.d/gnupg.amadeus-next
}

# Every aarch64 platform but a Mac, whose image brings its keyrings, makes its
# keyring at install, except in an image build, which leaves it to each
# machine's first boot (install/helpers/image-target.sh).
amadeus_pacman_keyring_wanted() {
  local platform
  platform=$(amadeus-hw-platform)
  [[ $platform == aarch64* && $platform != "aarch64-apple" ]] || return 1
  source "$AMADEUS_PATH/install/helpers/image-target.sh"
  ! { amadeus_image_init && amadeus_image_manifest_present; }
}

amadeus_pacman_keyring_start() {
  local next lock
  [[ ${AMADEUS_FIRST_INSTALL:-0} == "1" ]] || return 0
  amadeus_pacman_keyring_wanted || return 0
  amadeus_pacman_keyring_init
  next=$amadeus_pacman_keyring_next

  # --populate reads the keyrings this package installs.
  amadeus-pkg-add archlinuxarm-keyring

  rm -rf "$next" "$next.done" "$next.log"
  mkdir -p "$(dirname "$next")"
  # The lock is taken here and handed to the job, so a finish that comes before
  # the job is under way still waits for it.
  exec {lock}>"$next.lock"
  flock "$lock"
  (
    if pacman-key --gpgdir "$next" --init && pacman-key --gpgdir "$next" --populate; then
      touch "$next.done"
    fi
    # The keyring moves once it's done, so no agent may hold it open.
    gpgconf --homedir "$next" --kill all
  ) </dev/null >"$next.log" 2>&1 &
  exec {lock}>&-
}

amadeus_pacman_keyring_finish() {
  local next
  amadeus_pacman_keyring_init
  next=$amadeus_pacman_keyring_next

  if [[ -e $next.lock ]]; then
    flock "$next.lock" true
    cat "$next.log" 2>/dev/null || true
  fi

  if [[ -e $next.done ]]; then
    rm -rf "$amadeus_pacman_keyring"
    mv "$next" "$amadeus_pacman_keyring"
  else
    [[ ! -e $next ]] || rm -rf "$next"
    pacman-key --init
    pacman-key --populate
  fi

  rm -f "$next.lock" "$next.done" "$next.log"
}
