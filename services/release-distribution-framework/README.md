# Release & Distribution Framework

Enterprise Release & Distribution Framework Service (Prompt 080) —
creating, validating, signing, packaging, promoting, publishing, and
distributing every AI-IOS software release, across every channel from
nightly builds to long-term support lines.

Port `8051`. Database `aiios_release_distribution_framework`. Redis db `53`.

**This is the final prompt document in the docs/ sequence (000-080).**

## Ideas that shape everything here

**A linear lifecycle engine, distinct from the shared job engine used
everywhere else.** Every prior AI-IOS service in this build (076-079)
drives its central entity through the same PENDING/RUNNING/{SUCCEEDED,
FAILED} job shape. A release version does not fit that shape: it has no
"failed" branch, because a release can always be re-attempted — build
failure lives on the separate `ReleaseBuild` entity instead.
`app.release.engine` models a longer, purely linear pipeline instead:
DRAFT → VALIDATED → SIGNED → PUBLISHED → ARCHIVED, with a
`next_status_toward(current, target)` helper that lets
`ReleaseVersionService.publish()` walk a DRAFT release all the way to
PUBLISHED in one call — since docs/080 names no separate
`POST /releases/validate`/`POST /releases/sign` routes of its own —
while still publishing each intermediate event (`ReleaseValidated`,
`ReleaseSigned`, `ReleasePublished`) exactly as if each step had been
invoked individually. `app.build.engine` (renamed on disk to
`app.release_build.engine` — see "A `.dockerignore` collision" below)
is the familiar shared job engine, reused unmodified for
`ReleaseBuild`'s own PENDING→RUNNING→{SUCCEEDED,FAILED}.

**Publishing an already-published release is a no-op, not an error.**
Because the lifecycle has no failure branch, `_advance()`'s own loop
condition (`while status != target`) simply returns immediately if the
version is already at the target status — re-publishing is safe to
retry. What *is* a real error is trying to publish an `ARCHIVED`
version: `next_status_toward` refuses to walk backwards, so `_advance`
falls through to `validate_transition`, which reports the terminal
state and raises `TransitionRefusedError` — translated by the route
into a 400.

**A spec's own inconsistent vocabulary, bridged explicitly.** docs/080's
"RELEASE PROMOTION" section describes a maturity ladder in its own
prose — Development → QA → UAT → Production, Canary → Stable, Stable →
LTS — that doesn't map 1:1 onto `ReleaseChannelType`'s 12 actual values
(there is no distinct QA/UAT channel). `app.promotion.engine`'s
`ALLOWED_PROMOTIONS` adjacency dict resolves this by preserving the
literal Canary→Stable and Stable→LTS transitions exactly, and
generalizing the rest into this service's own
DEVELOPMENT→ALPHA→BETA→RELEASE_CANDIDATE→STABLE ladder — a deliberate
interpretation, documented in the engine's own module docstring.

**A single-hop `promote()`, with a lower-level `create()` kept
reachable for exactly one caller.** `POST /releases/promote` is the
only promotion route docs/080 names, so `ReleasePromotionService.
promote()` creates a promotion row and immediately completes-or-rejects
it based on `is_valid_promotion` — no separate approval workflow.
`create()` stays available on its own, leaving a promotion genuinely
`PENDING`; the only thing that ever reaches that state is
`PromotionApprovalTimeoutSweepWorker`'s own test setup and any future
approval-workflow caller, which is exactly why the worker exists at
all — a `promote()`-created promotion never sits `PENDING` long enough
to time out.

**Real computation next to a caller-reported boundary, within the same
supply-chain area.** `app.signing.engine.compute_checksum`/
`verify_checksum` do genuine `hashlib` SHA256/SHA512/MD5 work, since
hashing bytes the process already holds is real, cheap, executable
work. `ArtifactSignatureService`, immediately adjacent, accepts the
signature bytes as caller-supplied, since producing a real signature
needs a private signing key this service never holds — the same
boundary 077/079 draw across service boundaries, now drawn within one
service's own supply-chain code.

**Three edge-trigger shapes across five workers, chosen deliberately
per entity.** `LtsSupportExpirySweepWorker` and `EolScheduleSweepWorker`
each use a **persisted boolean flag** (`support_expiry_notice_sent`,
`deprecation_notice_sent`) — the entity is long-lived and entering the
warning window isn't itself a state transition, mirroring 075's/079's
own certificate-expiry precedent. `PromotionApprovalTimeoutSweepWorker`
needs no flag at all: once a promotion leaves `PENDING` (to `REJECTED`
or `COMPLETED`), its own `PENDING`-only query stops seeing it — an
**inherent status-query edge-trigger**, the same shape 079's
`CertificationExpirySweepWorker` uses.

**Organization discovery unions four independent activity sources.**
`StatisticsRollupWorker` unions org-ids from release versions, release
builds, release promotions, and downloads — an organization whose only
activity in a window was a download would otherwise never be rolled up
at all, the same gap prior rollup workers in this codebase had to be
closed.

**A `.dockerignore` collision, caught by the live e2e build, not by any
test.** The pure engine originally lived at `app/build/engine.py`. The
repo-root `.dockerignore` has `**/build/` (meant to exclude JS/TS build
output directories), which silently excluded this service's own
`app/build/` from the Docker build context — the container built
successfully but crashed on startup with
`ModuleNotFoundError: No module named 'app.build'`. Pytest, Ruff,
Black, and MyPy all pass with `app/build/` present on the host
filesystem, since none of them build a Docker image; only the live
container build surfaced it. Fixed by renaming the module to
`app/release_build/engine.py`, which collides with nothing generic.
**This is the same class of bug as the pytest `Test*`-prefix collision
found in Prompt 077 and the reserved-column-name class found earlier
in this build: a name that is perfectly reasonable in isolation
colliding with a generic pattern owned by different tooling.** Worth
checking early in any future service whose natural domain vocabulary
(`build`, `dist`, `node_modules`, `target`, `out`, `bin`) overlaps a
common build-artifact directory name.

**One fanned notification, seven direct.** `ReleasePublished` is the
only one of docs/080's eight notification kinds wired through
`NotifyingPublisher` — into Security Release, and only when the
published version's own `is_security_release` flag is set. The other
seven are called directly by the code that observes the underlying
fact: New Release (on every creation), LTS Release (on designating a
new LTS line), Promotion Complete (on a completed promotion), Release
Failure (on a failed build), EOL Warning (by both the LTS and EOL
sweep workers, each edge-triggered), Patch Available (on publishing a
subsequent LTS-channel release), Critical Update (on publishing a
security release specifically on STABLE/LTS — the strongest signal
combination).

**Every route requires an administrator role.** Release creation,
promotion, and publishing are internal engineering signals, not
customer-facing data — the same administrator-heavy routing every
adjacent infrastructure-framework service in this build (075-079)
established.

## Architecture

- `app/models/` — 18 tables across 11 files: `channels.py`
  (ReleaseChannelConfig), `releases.py` (ReleaseVersion), `builds.py`
  (ReleaseBuild), `packages.py` (ReleasePackage, ReleaseArtifact),
  `promotions.py` (ReleasePromotion), `distribution.py`
  (ReleaseDistribution, ReleaseRegion), `downloads.py`
  (DownloadStatistic), `supply_chain.py` (ArtifactChecksum,
  ArtifactSignature, SbomPublication), `notes.py` (ReleaseNote),
  `lifecycle.py` (LtsVersion, EolSchedule), `reporting.py`
  (ReleaseStatistic, ReleaseReport, ReleaseAudit).
- 10 pure engines, each hand-verified before any pytest was written
  (42 checks, zero defects): `app/release/engine.py` (the linear
  lifecycle), `app/release_build/engine.py` (the shared job engine),
  `app/signing/engine.py` (real checksum computation), `app/promotion/
  engine.py` (the bridged promotion adjacency), `app/distribution/
  engine.py` (air-gapped/region classification), `app/lts/engine.py`
  and `app/eol/engine.py` (warning-window detection), `app/download/
  engine.py` (rate computation), `app/notes/engine.py` (security/
  breaking classification), `app/analytics/engine.py` (build success
  rate, promotion success rate, release health score).
- `app/services/` — one service per table-group plus
  `notifications.py` (`ReleaseNotifier` + `NotifyingPublisher`),
  `audit.py` (the single write path for `release_audit`), `bundle.py`
  (the shared repository bundle).
- `app/api/releases.py` — the 12 REST routes exactly as docs/080 lists
  them, every one gated behind `require_administrator`.
- `app/workers/` — 5 leader-elected background jobs: release build
  timeout sweep, promotion approval timeout sweep (inherently
  edge-triggered via status), LTS support expiry sweep and EOL
  schedule sweep (each edge-triggered via a persisted flag), statistics
  rollup.
- 9 domain events (`app/events/domain_events.py`), 8 notification
  kinds (`app/services/notifications.py`) — 1 fanned from an event
  (`ReleasePublished` → Security Release, gated on
  `is_security_release`), 7 called directly.

## Testing

129 tests (42 engine, 13 repository, 23 service, 11 worker, 11 API, 27
deps/notifications, plus 2 smoke tests) at 96.58% coverage, against
real PostgreSQL and Redis. Ruff, Black, and MyPy (scoped to `app/` +
`main.py`) all clean.

Live Docker e2e confirmed: all 5 workers registered on startup and
scheduler leadership acquired; health/readiness real; a release
channel seeded directly via `psql` (no create-channel route exists by
design), then a release version created, published (walking its full
DRAFT→VALIDATED→SIGNED→PUBLISHED lifecycle in one HTTP call), and
promoted canary→stable — all through real HTTP with a real
RS256-signed JWT. **Two data-writing workers confirmed firing fully
autonomously on their very next 60-second scheduled tick after their
respective source rows were backdated/seeded via `psql`, never
manually triggered**: the build timeout sweep worker failed a
3-hours-stuck `RUNNING` build (`failed: 1`, `error_message: "Release
build timed out."`), and the LTS support expiry sweep worker flagged a
newly-in-window LTS line (`notified: 1`, `support_expiry_notice_sent`
persisted `true`) — both confirmed via `psql` re-reads and via the
container's own structured logs, which additionally showed all 5
workers (including promotion approval timeout sweep, EOL schedule
sweep, and statistics rollup) ticking cleanly on both the first and
second 60-second intervals. RBAC confirmed (401 no token, 403 non-admin
role, 200 admin). Database truncated and container removed after.
