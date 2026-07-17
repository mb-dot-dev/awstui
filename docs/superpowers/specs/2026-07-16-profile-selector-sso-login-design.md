# AWS profile selector and SSO login

**Date:** 2026-07-16
**Branch:** `feature/profile-selector-and-sso-login`

## Goal

Two related credential-experience features:

1. When the app starts without an AWS profile selected, show a profile picker before the
   service menu.
2. When AWS credentials are expired or missing on an SSO profile, let the user complete
   an SSO login from inside the app (via the SSO OIDC device flow) and retry.

## Non-goals

- Switching profiles mid-session (the picker appears only at startup).
- An upfront credential validation call at startup (errors surface lazily, as today).
- Depending on the AWS CLI; login runs in-process via boto3's `sso-oidc` client.
- Login support for non-SSO profiles (there is nothing to log in to; they keep the
  existing error hint).

## Design

### AWS layer: `src/awst/aws/profiles.py` (new)

Owns all profile/credential-environment access, keeping boto3/botocore out of screens:

- `active_profile() -> str | None` — `AWS_PROFILE` or `AWS_DEFAULT_PROFILE` from the
  environment (in that order), else `None`.
- `available_profiles() -> list[str]` — `boto3.Session().available_profiles`.
- `sso_config(name: str | None) -> SsoConfig | None` — resolves the profile's SSO
  settings from its parsed config (botocore `Session.full_config`) into a frozen
  `SsoConfig` model: `start_url`, `sso_region`, and `session_name` (`None` for legacy
  inline `sso_*` profiles, the `[sso-session <name>]` section name for modern profiles,
  with `start_url`/`sso_region` read from that section). Returns `None` when the profile
  has no SSO configuration ("is this an SSO profile?" is `sso_config(...) is not None`).
  `None` checks the `default` profile.
- `select_profile(name: str) -> None` — sets `os.environ["AWS_PROFILE"]`. All gateways
  are built lazily from a fresh `boto3.Session()`, so they pick up the selection with no
  gateway changes.

### Error model

- New `CredentialsError(AwsError)` subclass in `models.py`.
- `errors.py` maps `NoCredentialsError`, `SSOTokenLoadError`, `TokenRetrievalError`, and
  `UnauthorizedSSOTokenError` to `CredentialsError` (message and hint unchanged). Screens
  can then recognize credential failures without string matching.

### Profile selection at startup

- New screen `src/awst/screens/profiles.py` — `ProfileSelectScreen`, an `OptionList` of
  profile names styled like `HomeScreen` ("Select an AWS profile"), `q` quits. It receives
  a plain `list[str]` of names; selecting one reports the choice back to the app, which
  calls `select_profile` and switches to `HomeScreen`.
- `AwstApp.on_mount()`: if `active_profile()` is `None` and `available_profiles()` is
  non-empty, push `ProfileSelectScreen`; otherwise push `HomeScreen` as today. No profiles
  configured at all → straight to home (the existing credential-error path covers it).
- The app subtitle shows the active profile so it is always visible in the header.

### AWS layer: `src/awst/aws/sso.py` (new)

An `SsoLoginGateway` in the existing gateway style, wrapping a boto3 `sso-oidc` client
built for the profile's `sso_region`. The frozen models it exchanges (`SsoConfig`,
`DeviceAuthorization`, `SsoToken`) live in `aws/models.py` with the rest, as does the
`SlowDownError` exception (screens import exceptions only from `models.py`). It drives
the OIDC device-authorization flow:

- `start_device_authorization(config: SsoConfig) -> DeviceAuthorization` — calls
  `register_client` (client name `awst`, type `public`) then
  `start_device_authorization`, returning a frozen model with `verification_uri`,
  `verification_uri_complete`, `user_code`, `device_code`, `interval`, `expires_at`,
  plus the registration's `client_id`/`client_secret`/`registration_expires_at`.
- `poll_token(authorization: DeviceAuthorization) -> SsoToken | None` — one
  `create_token` attempt with the device-code grant. Returns `None` while
  `AuthorizationPendingException`; raises `SlowDownError` on `SlowDownException` (the
  poller then adds 5 seconds to its interval); raises `AwsError` on
  `ExpiredTokenException` or any other failure. On success returns an `SsoToken`
  (`access_token`, `expires_at`, `refresh_token` when present).
- `write_token_cache(config: SsoConfig, authorization: DeviceAuthorization, token: SsoToken) -> None` —
  persists the token where botocore's credential resolver reads it:
  `~/.aws/sso/cache/<sha1>.json` (cache directory overridable for tests). The cache key
  is the SHA-1 of the session name for `sso-session` profiles, else of the start URL.
  The JSON carries `accessToken`, `expiresAt` (UTC ISO-8601 `Z` format), `region`,
  `startUrl`, and — for `sso-session` profiles — `clientId`, `clientSecret`,
  `registrationExpiresAt`, and `refreshToken` so botocore can auto-refresh.
  This file format mirrors botocore/AWS CLI internals rather than a documented public
  contract; the format is centralized in this one function and covered by tests so a
  botocore upgrade that changes expectations is caught early.

All botocore exceptions are translated through the existing `map_botocore_error`.

### SSO login from the error state

- `ResourceListScreen` gains a binding `l` — Login, shown dynamically (Textual
  `check_action`) only when the last failure was a `CredentialsError` **and**
  `sso_config(active_profile())` resolves. When available, the error panel appends
  "Press l to log in via AWS SSO."
- `action_login` pushes a new modal, `SsoLoginScreen`
  (`src/awst/screens/sso_login.py`), which owns the interactive flow — no terminal
  suspension needed:
  1. On mount, a thread worker calls `start_device_authorization`, then the modal shows
     the verification URL and user code, and opens the browser via `webbrowser.open`
     (best-effort; the URL and code stay visible for manual use, e.g. over SSH).
  2. The worker polls `poll_token` every `interval` seconds (respecting slow-down
     requests) until success, expiry, or cancel (`escape` dismisses and cancels the
     worker).
  3. On success it writes the token cache and dismisses with `True`; the list screen
     then runs `action_refresh()`. On failure or cancel it dismisses with `False` and
     the error panel stays (failures are also surfaced via `notify()`).
- Mid-session expiry is covered by the same path: a failed refresh raising
  `CredentialsError` enables the binding.
- `AwstApp` exposes a lazily-built `SsoLoginGateway` factory keyed by the resolved
  `SsoConfig` (injectable for tests, like the service gateways), so screens never touch
  boto3.

### Testability seam

Screens never import boto3/botocore, so profile helpers reach screens the same way
gateways do: `AwstApp` calls the `aws.profiles` functions directly (they read
process env vars and botocore config, so tests exercise them hermetically through
real config files rather than injection — this beats a fake, since it also exercises
real botocore config parsing). Only the SSO gateway factory (`sso_gateway_factory`)
is an injectable constructor parameter. `ProfileSelectScreen` takes a plain list of
names.

## Error handling

- No profiles in `~/.aws/config` → skip the picker.
- Profile has no resolvable SSO configuration → the Login binding stays hidden; the
  existing error hint is all the user sees.
- Device authorization expires before the user approves → the modal reports it and
  offers retry (pressing `l` again restarts the flow).
- User cancels (escape) → modal dismisses quietly; error panel stays.
- `register_client`/`create_token` API failures → mapped through `map_botocore_error`
  and shown via `notify()`; panel stays.
- Login succeeds but credentials still fail → refresh lands back on the error panel with
  the binding still available.
- Browser cannot be opened (headless/SSH) → the verification URL and code shown in the
  modal are sufficient; `webbrowser.open` failures are ignored.

## Testing

- `tests/test_profiles.py` — `active_profile` env handling; `sso_config` against a temp
  `AWS_CONFIG_FILE` with SSO, non-SSO, and `sso_session`-style profiles.
- `tests/test_sso_gateway.py` — `SsoLoginGateway` against a botocore `Stubber` (moto
  does not model `sso-oidc`): device authorization happy path, pending → token polling,
  slow-down, expiry, and API errors. `write_token_cache` against a temp cache dir:
  correct SHA-1 filename and JSON shape for both legacy and `sso-session` profiles.
- `tests/test_profile_select_screen.py` — pilot tests: no `AWS_PROFILE` + injected
  profile list shows the picker; selection sets the env var and lands on home;
  `AWS_PROFILE` set skips the picker.
- `tests/test_sso_login_screen.py` — pilot tests with a `FakeSsoLoginGateway`
  (`tests/fakes.py`): modal shows URL and code; successful poll writes the cache,
  dismisses `True`, and triggers a list refresh; expiry shows the retry state; escape
  cancels.
- List-screen login tests (existing style, fake gateway raising `CredentialsError`):
  panel shows the login hint and `l` is active only for SSO-configured profiles.
- `test_errors.py` extended for the `CredentialsError` mapping.
