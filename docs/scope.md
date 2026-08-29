# Colosseum Core scope

Colosseum Core is the plugin-oriented runtime for Python-based test automation.

## In scope

- `@command`, `@measurement`, and `@verification` evidence decorators
- run context, result aggregation, exit policy, and `col.endex()`
- TOML loading, normalization, warnings, and plugin-owned config section
  contracts
- runtime plugin entry-point discovery
- dynamic `col.<namespace>` plugin access
- single-test and suite execution
- SQLite evidence, logs, summaries, output paths, and artifact registration
- optional GUI launcher
- documentation generation (handwritten guides + config reference)

## Out of scope

The following belong in independently versioned plugins or end-user projects:

- device and instrument APIs
- transports and protocol implementations
- host, network, SSH, and operating-system inspection
- vendor models, hardware fixtures, and simulation definitions
- bench-specific examples and configuration
- aggregate/offline bundles spanning multiple distributions

## Compatibility boundary

Plugins integrate through `colosseum.plugins`,
`PluginRegistry`, `ConfigSectionSpec`, decorators, and the public `colosseum`
API.
Core CI validates these contracts with test doubles and must pass without
first-party
plugins or sibling repositories installed.
