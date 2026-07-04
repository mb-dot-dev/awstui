# CloudFormation stack list — design

**Date:** 2026-07-04
**Status:** Approved

## Goal

The first real feature of awst: a read-only CloudFormation stack list. Beyond the
feature itself, this establishes the app's foundations — screen navigation, the AWS
client layer, and the testing approach — that later pages (stack details, S3 buckets,
SQS queues, …) will follow.

## Scope

**In scope (v1):**

- A home screen listing services, with only CloudFormation enabled.
- A stack list screen: all stacks in the account/region, with local filtering,
  manual refresh, and color-coded statuses.
- AWS credentials/region resolved via boto3's default chain only (env vars,
  `AWS_PROFILE`, `~/.aws/config`, SSO). No in-app profile/region switching.

**Out of scope (later):**

- Stack details page (pressing `enter` on a stack does nothing in v1).
- Any mutating actions (delete, update).
- Server-side paging, auto-refresh, CLI flags for profile/region.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| SDK | boto3 (sync) behind a gateway, run in Textual thread workers | Best-supported SDK, full SSO, `boto3-stubs` typing; thread workers are Textual's documented pattern for blocking IO. aiobotocore rejected for dependency pinning and typing friction; the gateway boundary hides sync-vs-async anyway. |
| API call | `DescribeStacks` paginator, run to exhaustion | Excludes deleted stacks by default (unlike `ListStacks`) and includes descriptions. |
| Loading model | Fetch all pages up front, filter locally | Instant filtering; fine to a few thousand stacks. |
| Models | Frozen stdlib dataclasses (`slots=True`) | Data arrives already parsed/typed from botocore; no serialization needs. Pydantic deferred until a genuinely untrusted boundary appears (e.g. a config file). |
| Navigation | Service menu home screen first | Establishes the multi-service navigation shell now. |

## Architecture

```
src/awst/
├── __init__.py           # main() → AwstApp().run()
├── app.py                # AwstApp(App): installs HomeScreen, owns the AWS session/gateways
├── aws/
│   ├── __init__.py
│   ├── models.py         # StackSummary dataclass; AwsError exception
│   └── cloudformation.py # CloudFormationGateway: list_stacks() → list[StackSummary]
└── screens/
    ├── __init__.py
    ├── home.py           # HomeScreen: service menu
    └── stacks.py         # StackListScreen: DataTable of stacks with filter + refresh
```

- `skeleton_app.py` and `tests/test_skeleton_app.py` are deleted, replaced by the
  real app and its tests.
- `AwstApp` owns a single `boto3.Session`, created lazily on first use (Session
  construction doesn't validate credentials, so startup never blocks on AWS). It
  hands gateway objects to screens; **screens never import boto3 or botocore**.
- `CloudFormationGateway` has one method, `list_stacks()`, which runs the
  `DescribeStacks` paginator to exhaustion and maps each stack to a `StackSummary`.
- `StackSummary` fields: `name`, `status`, `created`, `updated`, `description`.
  `updated` falls back to `CreationTime` when `LastUpdatedTime` is absent
  (never-updated stacks).
- Extension path: each future service adds one gateway module + one screen module +
  a home-menu entry; existing files change only at the menu list.

**New dependencies:** `boto3` (runtime); `boto3-stubs[cloudformation]` (dev, for
`ty`) and `moto` (dev, for gateway tests).

## Screens

### HomeScreen

```
┌─ awst ─────────────────────────────────────┐
│  Select a service                          │
│                                            │
│  ▸ CloudFormation   Stacks                 │
│    S3               Buckets     (soon)     │
│    SQS              Queues      (soon)     │
│                                            │
│ ↑↓ navigate · enter open · q quit          │
└────────────────────────────────────────────┘
```

- An `OptionList` driven by a data list of
  `(name, screen_factory, enabled)` entries. Only CloudFormation is enabled;
  S3/SQS are greyed-out, non-selectable roadmap hints.
- `enter` pushes `StackListScreen`; `q` quits. Key hints via the standard
  `Footer` widget and `BINDINGS`.

### StackListScreen

```
┌─ CloudFormation stacks ──────────── 42 stacks ─┐
│ / filter: prod▁                                │
│ Name              Status            Updated    │
│ prod-api          UPDATE_COMPLETE   2h ago     │
│ prod-network      CREATE_COMPLETE   3d ago     │
│ ↑↓ move · / filter · r refresh · esc back      │
└────────────────────────────────────────────────┘
```

- `DataTable` with columns **Name, Status, Created, Updated**. Description is
  omitted (belongs on the future details page). Timestamps render as relative
  age ("2h ago").
- Status cell color-coding: green `*_COMPLETE`, yellow `*_IN_PROGRESS`,
  red `*_FAILED` / `ROLLBACK*`.
- Rows sorted by name, keyed by stack name (cursor survives refresh; `enter`
  wiring for the future details screen is trivial).
- `/` focuses a filter `Input` above the table; live case-insensitive substring
  match on the name. Header shows the total count, or "n of m" while filtering.
  `esc` in the filter clears it and refocuses the table; `esc` in the table pops
  back to Home.
- `r` re-fetches. A loading indicator shows during fetch; on refresh, old rows
  stay visible until new data lands.

## Data flow

1. `StackListScreen` receives the gateway via its constructor. On mount it starts
   a thread worker (`@work(thread=True, exclusive=True)`) calling
   `gateway.list_stacks()`.
2. The worker's result becomes the canonical unfiltered list; rows render through
   the current filter; cursor restored by row key.
3. `exclusive=True` means a refresh spammed mid-flight cancels the previous fetch
   rather than racing it.
4. Filtering is a pure re-render of the stored list — no worker involved.

## Error handling

- The gateway catches botocore exceptions at its boundary and raises a single
  domain exception, `AwsError(message, hint)`:
  - `NoCredentialsError` / expired SSO token → hint "check AWS_PROFILE or run
    `aws sso login`"
  - `ClientError` AccessDenied → the IAM error message
  - `EndpointConnectionError` / timeouts → "check network / region"
  - other botocore exceptions → generic message with exception text
- Initial-load failure: the table area is replaced by an error panel (message +
  hint); `r` retries, `esc` still goes back.
- Refresh failure: keep the stale table, surface the error as a `notify()` toast.
- Non-AWS exceptions are not caught — crash loudly during development.

## Testing

Two layers, matching the gateway boundary:

**UI tests** (Textual `run_test()` pilot + pytest-asyncio, the existing pattern).
A `FakeCloudFormationGateway` returns canned `StackSummary` lists or raises
`AwsError`, injected through the same constructor parameter as the real gateway.
Cases:

- Home menu renders; disabled entries not selectable; `enter` pushes the stack
  list; `q` quits.
- Stack list renders one row per stack, correct header count, correct status
  styling.
- Filter narrows rows live, shows "n of m", clears on `esc`.
- `r` re-fetches and shows updated data.
- Initial-load failure shows the error panel; `r` retries and recovers.
- Refresh failure keeps stale rows and shows a toast.

**Gateway tests** (`moto`'s `mock_aws`, no network). Stacks are created through
moto's mocked CloudFormation backend, then `list_stacks()` is asserted against
them — exercising the real boto3 request/response path:

- Multiple stacks created in moto → one combined, name-mappable list. (moto
  doesn't expose page boundaries, so boto3's paginator mechanics are trusted
  as SDK behavior rather than forced across pages.)
- Field mapping, including absent `LastUpdatedTime` → falls back to `CreationTime`.
- Exception mapping: `ClientError` cases via moto where producible; credential
  and connection errors (`NoCredentialsError`, `EndpointConnectionError`) by
  constructing the botocore exceptions directly against the mapping function.

Coverage must clear the existing 75% gate; `make test` (lint + unit) remains the
definition of done.
