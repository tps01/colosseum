# Vulture whitelist: unavoidable dynamic / entry-point surfaces only.
# fmt: off

# Plugin registration entry points
register  # colosseum_*.__init__

# Public lazy namespaces (resolved at runtime)
equipment  # colosseum.__init__
shared  # colosseum.__init__
io  # colosseum.__init__
host  # colosseum.__init__
