# The Spark profile installs these optional applications; Workbench account
# access is requested on first launch.
if amadeus-pkg-present nvidia-ai-workbench; then
  # This edits amadeus-desktop' daemon.json; later defaults arrive as .pacnew.
  nvidia-ctk runtime configure --runtime=docker
fi

if amadeus-pkg-present dgx-dashboard; then
  systemctl enable dgx-dashboard.service
  # Deferred setup runs after boot queued the enabled services.
  if [[ ${AMADEUS_IMAGE_DEFERRED_HARDWARE:-} == "1" ]]; then
    systemctl start --no-block dgx-dashboard.service || true
  fi
fi
