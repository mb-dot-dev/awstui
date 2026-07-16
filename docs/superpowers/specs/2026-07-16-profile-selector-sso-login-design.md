# AWS profile selector and SSO login

**Date:** 2026-07-16
**Branch:** `feature/profile-selector-and-sso-login`

## Goal

Two related credential-experience features:

1. When the app starts without an AWS profile selected, show a profile picker before the
   service menu.
2. When AWS credentials are expired or missing on an SSO profile, let the user run
   `aws sso login` from inside the app and retry.

## Non-goals

- Switching profiles mid-session (the picker appears only at startup).
- An upfront credential validation call at startup (errors surface lazily, as today).
- Implementing the SSO OIDC device flow in-process; the AWS CLI does the login.
- Login support for non-SSO profiles (there is no CLI login command for them; they keep
  the existing error hint).

## Design

### AWS layer: `src/awst/aws/profiles.py` (new)

Owns all profile/credential-environment access, keeping boto3/botocore out of screens:

- `active_profile() -> str | None` — `AWS_PROFILE` or `AWS_DEFAULT_PROFILE` from the
  environment (in that order), else `None`.
- `available_profiles() -> list[str]` — `boto3.Session().available_profiles`.
- `is_sso_profile(name: str | None) -> bool` — true when the profile's parsed config
  (botocore `Session.full_config`) contains any `sso_*` key or an `sso_session`
  reference. `None` checks the `default` profile.
- `select_profile(name: str) -> None` — sets `os.environ["AWS_PROFILE"]`. All gateways
  are built lazily from a fresh `boto3.Session()`, so they pick up the selection with no
  gateway changes.
- `sso_login(profile: str | None) -> LoginResult` — runs `aws sso login`
  (plus `--profile <name>` when given) via `subprocess.run` with an argument list, no
  shell. Distinguishes success, non-zero exit, and `FileNotFoundError` (AWS CLI not
  installed) so the UI can report each case.

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

### SSO login from the error state

In `ResourceListScreen`:

- New binding `l` — Login, shown dynamically (Textual `check_action`) only when the last
  failure was a `CredentialsError` **and** `is_sso_profile(active_profile())` is true.
- When the binding is available, the error panel appends "Press l to log in via AWS SSO."
- `action_login`:
  1. `with self.app.suspend():` run `sso_login(active_profile())` — the terminal is
     restored and the CLI's device-code/browser flow works as usual.
  2. Success → `action_refresh()` (restores the table and refetches).
  3. Failure → `notify()` with the reason ("AWS CLI not found" vs. "login failed");
     the error panel stays.
- Mid-session expiry is covered by the same path: a failed refresh raising
  `CredentialsError` enables the binding.

### Testability seam

Screens never import boto3/botocore, so profile helpers reach screens the same way
gateways do: `AwstApp` takes injectable constructor parameters defaulting to the real
`aws.profiles` functions, and screens call them via the app. `ProfileSelectScreen` takes
a plain list of names.

## Error handling

- No profiles in `~/.aws/config` → skip the picker.
- `aws` CLI not installed → pressing `l` notifies "AWS CLI not found"; panel stays.
- Login succeeds but credentials still fail → refresh lands back on the error panel with
  the binding still available.
- Login exits non-zero (user cancels the browser flow) → notify; panel stays.

## Testing

- `tests/test_profiles.py` — `active_profile` env handling; `is_sso_profile` against a
  temp `AWS_CONFIG_FILE` with SSO, non-SSO, and `sso_session`-style profiles; `sso_login`
  with a mocked `subprocess.run` (success, failure, CLI missing).
- `tests/test_profile_select_screen.py` — pilot tests: no `AWS_PROFILE` + injected
  profile list shows the picker; selection sets the env var and lands on home;
  `AWS_PROFILE` set skips the picker.
- List-screen login tests (existing style, fake gateway raising `CredentialsError`):
  panel shows the login hint and `l` is active only for SSO profiles; pressing `l` with a
  stubbed `sso_login`/`suspend` refreshes on success and notifies on failure.
- `test_errors.py` extended for the `CredentialsError` mapping.
