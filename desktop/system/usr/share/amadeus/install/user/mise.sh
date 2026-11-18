# Build the lazy shims for Amadeus's default tools and the account dispatchers,
# both declared by /etc/mise/conf.d, without resolving versions over the network.
MISE_OFFLINE=true mise reshim --system
MISE_OFFLINE=true mise reshim
