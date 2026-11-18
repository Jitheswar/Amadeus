# Chrome ships in the base packages, so it never goes through
# amadeus-install-browser, and fresh installs mark every migration as already
# applied. /etc/skel gives it its flags, but the native messaging hosts the
# bundled extensions talk to have to be registered here.
amadeus-install-chromium-copy-url
amadeus-install-chromium-ytdlp
