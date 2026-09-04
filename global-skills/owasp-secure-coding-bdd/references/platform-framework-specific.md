# Platform & Framework-Specific Security

Covers: NodeJS Security, Django Security, Ruby on Rails Security, Mobile Application Security (iOS/Android).

## Node.js
- Avoid `eval()`, `new Function()`, and `child_process.exec()` with any string built from user input — use `execFile`/`spawn` with an argument array instead (see injection reference).
- Keep dependencies patched — Node's ecosystem has a very high transitive-dependency count; run `npm audit` in CI (see dependency reference) and consider a lockfile-based reproducible install (`npm ci`, not `npm install`, in CI/deploy).
- Set security-relevant HTTP headers via a maintained middleware (e.g., `helmet` for Express) rather than hand-rolling each header.
- Avoid running the Node process as root in production/containers (see container reference).
- Be careful with prototype pollution: validate/sanitize when merging user-controlled objects into application objects (e.g., a naive deep-merge of a request body into config), since polluting `Object.prototype` can have wide-reaching effects; use libraries with known prototype-pollution fixes and avoid recursive merge of untrusted keys like `__proto__`/`constructor`/`prototype`.
- Use environment-based configuration for secrets (see cryptography-secrets.md), never commit `.env` files.

## Django
- Never set `DEBUG = True` in production — Django's debug page reveals settings, source snippets, and environment details to anyone who triggers an error.
- Keep `SECRET_KEY` out of source control and unique per environment; it's used for session signing, so a leaked key allows session forgery.
- Django's ORM parameterizes queries by default — the risk is dropping to raw SQL (`.raw()`, `cursor.execute()`) with string-formatted input; apply the same parameterization discipline as any raw SQL (see injection reference).
- Use Django's built-in CSRF middleware (`django.middleware.csrf.CsrfViewMiddleware`) rather than disabling it for convenience; if disabling it for a specific API view, ensure that view uses a non-cookie auth scheme instead (see CSRF reference for when it's actually needed).
- Set `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`, and `CSRF_COOKIE_SECURE` to `True` in production settings.
- Restrict `ALLOWED_HOSTS` to the actual expected hostnames rather than leaving it wildcarded.

## Ruby on Rails
- Rails' ActiveRecord parameterizes queries by default — the risk is raw SQL fragments (`where("name = '#{params[:name]}'")`) instead of the parameterized form (`where("name = ?", params[:name])`); always use the parameterized/hash form.
- Use Strong Parameters (`params.require(...).permit(...)`) on every controller action that accepts input, to prevent mass assignment (see mass assignment section in the API reference file) — never `params.permit!` (permits everything) on models with sensitive fields.
- Keep `config.force_ssl = true` in production.
- Don't disable Rails' built-in CSRF protection (`protect_from_forgery`) without substituting an equivalent control for that endpoint.
- Be cautious with `Marshal.load`, `YAML.load` (use `YAML.safe_load` instead), and `Kernel#eval` on any user-influenced data (see deserialization reference).
- Keep the Rails version and gems current — Rails has had several high-impact CVEs (deserialization, mass assignment) that are fixed in current versions but still actively exploited against out-of-date apps.

## Mobile application security (iOS & Android)
- Never hardcode API keys, credentials, or encryption keys in the compiled app binary — anything in the app package can be extracted by an attacker with the APK/IPA in hand. Fetch secrets from a backend at runtime, scoped to the authenticated user/session, not embedded at build time.
- Use platform secure storage for tokens/credentials: Android Keystore-backed `EncryptedSharedPreferences`, iOS Keychain — never plain `SharedPreferences`/`UserDefaults` or files on external/unencrypted storage for sensitive data.
- Enforce certificate pinning for API calls carrying sensitive data if the threat model includes on-path attackers (public wifi, rooted/jailbroken device MITM tooling) — balanced against the operational cost of pin rotation.
- Validate all input server-side regardless of client-side validation in the app — a modified/rooted client can send anything directly to the API, bypassing the app's UI entirely.
- Don't rely on client-side root/jailbreak detection as a security control on its own — it's a speed bump, not access control; the authoritative checks must be server-side.
- Disable sensitive data appearing in screenshots/app-switcher previews for screens showing credentials or financial data (platform-specific: `FLAG_SECURE` on Android, a cover view on iOS backgrounding).
- Apply the same authentication/session/authorization discipline from the other reference files to the mobile app's backend API — the mobile client is just another API consumer from the server's point of view and must not be trusted more than a web client.

## BDD security scenario patterns

```gherkin
@security
Scenario: Application refuses to start in debug mode in production environment
  Given the environment is set to "production"
  When the application starts with DEBUG enabled
  Then startup fails or debug mode is forced off

@security
Scenario: Mass assignment is blocked by strong parameters
  Given a controller action uses permitted parameters "name, email"
  When a request includes an additional field "admin: true"
  Then the admin field is ignored and not persisted

@security
Scenario: Mobile app does not store auth token in plaintext local storage
  Given a user logs into the mobile app
  Then the auth token is stored using platform secure storage (Keychain/Keystore-backed), not plaintext files or unencrypted preferences

@security
Scenario: Mobile client input is still validated server-side
  Given a request bypasses the mobile app UI and calls the API directly with invalid data
  Then the server rejects it with the same validation as if it came through the app
```
