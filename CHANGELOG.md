# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3] - 2025-03-12
### Added
 - Verbosity flags (-v and -q) to sync commands

### Changed
 - Output of the sync commands is now flushed after each message

## [1.2] - 2025-03-06
### Added
 - Provide pas-db-migrate command for migrating database
 - Add support for enqueing objects by ids to deferred-enqueue-objects
 - Allow using PostgreSQL via unix socket
 - Allow configuring database via URL
 - Allow configuring Redis connection via URL

### Changed
 - Rename the dir inside SIP packages from "sip" to "data"
 - Change license to LGPLv3
 - Use asyncio.run instead of get_event_loop in sync scripts
 - Improve the run_test.sh worker runner script
 - Simplify database fixtures in tests
 - Switch from setup.py to pyproject.toml for packaging

## [1.1] - 2020-08-04
### Added
 - Add `deferred-enqueue-objects` script for enqueuing objects using a background RQ job.

### Changed
 - Increase default sync window for `sync-processed-sips` from 11 days to 31 days.

## 1.0 - 2020-06-17
### Added
 - First release.

[1.1]: https://github.com/finnish-heritage-agency/passari-workflow/compare/1.0...1.1
[1.2]: https://github.com/finnish-heritage-agency/passari-workflow/compare/1.1...1.2
[1.3]: https://github.com/finnish-heritage-agency/passari-workflow/compare/1.2...1.3
