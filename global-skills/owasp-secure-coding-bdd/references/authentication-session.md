# Authentication & Session Management

Covers: Authentication, Password Storage, Session Management, Multifactor Authentication, Forgot Password/Credential Recovery, Credential Stuffing.

## Password handling
- Hash passwords with **Argon2id** (preferred), or **bcrypt**/**scrypt** if the platform lacks Argon2 support. Never MD5, SHA-1, SHA-256 alone, or any fast general-purpose hash — those are crackable at billions of guesses/second on commodity GPUs.
- Use a unique random salt per password (handled automatically by Argon2id/bcrypt/scrypt libraries — don't roll your own).
- Enforce a minimum length (12+ characters recommended) over complexity rules (arbitrary "must contain a symbol" rules push users toward predictable patterns). Do not enforce a maximum length below 64 characters.
- Never log passwords, even at debug level. Never send passwords back in any response, including in "confirm your details" emails.
- On password change, invalidate all other active sessions/tokens.

## Login flow
- Return the **same generic error** ("invalid username or password") for both "user doesn't exist" and "password wrong" — never reveal which one was incorrect (prevents username enumeration).
- Enforce this same generic-error/uniform-timing principle on the password-reset and MFA flows too.
- Rate-limit login attempts per account and per source IP (e.g., exponential backoff or lockout after N failures) to blunt credential stuffing and brute force. Log repeated failures with source IP/timestamp for detection.
- Consider CAPTCHA or proof-of-work after repeated failures, not from the first attempt (avoid punishing legitimate users).
- Never allow authentication decisions to be made client-side only — always re-verify server-side even if a client-side check exists for UX.

## Multi-factor authentication (MFA)
- Support MFA (TOTP is the pragmatic default) for any account with elevated privileges or sensitive data access; make it available to all users.
- Store TOTP secrets encrypted at rest, not in plaintext.
- Rate-limit MFA code submission attempts (6-digit TOTP codes are brute-forceable without this).
- Provide backup/recovery codes generated server-side and shown once; hash them at rest like passwords.

## Session management
- Generate session IDs with a cryptographically secure random generator, at least 128 bits of entropy.
- Set cookies with `HttpOnly` (blocks JS access, mitigates XSS token theft), `Secure` (HTTPS only), and `SameSite=Strict` or `Lax` (mitigates CSRF).
- Regenerate the session ID on privilege change (login, logout, privilege elevation) — never reuse a pre-authentication session ID after login (session fixation).
- Set both an idle timeout (e.g., 15-30 min for sensitive apps) and an absolute session lifetime, enforced server-side.
- Provide an explicit logout that invalidates the session server-side, not just a client-side cookie clear.
- For token-based auth (JWT), prefer short-lived access tokens (minutes) with a separate refresh token, validate signature and `exp`/`iss`/`aud` claims on every request, and support server-side revocation (a deny-list or short expiry) — a JWT that's just "trust the signature forever" cannot be revoked if compromised.

## Security questions (avoid if possible)
- Prefer not to use "security questions" (mother's maiden name, first pet, etc.) as a standalone recovery/verification factor — answers are frequently guessable, publicly discoverable (social media), or have a small real-world set of possible answers. If required for legacy/compliance reasons, treat them as one weak factor combined with something stronger (a verified email/SMS/authenticator step), never as a sole gate for account recovery or step-up authentication.

## Forgot-password / account recovery
- Reset tokens must be single-use, cryptographically random, and short-lived (15-60 min).
- Don't reveal whether an email/username exists — respond with the same message ("if an account exists, a reset email has been sent") regardless.
- Invalidate the reset token immediately after use, and invalidate all other active sessions once the password is actually changed.

## BDD security scenario patterns

```gherkin
@security
Scenario: Login failure does not reveal whether the account exists
  When a user submits a nonexistent username with any password
  Then the response message is identical to a wrong-password response

@security
Scenario: Repeated failed logins trigger rate limiting
  Given 5 failed login attempts for the same account within 1 minute
  When a 6th attempt is made
  Then the request is rejected with a rate-limit response
  And no further password check is performed

@security
Scenario: Session cookie has secure attributes
  Given a user has logged in successfully
  Then the session cookie has HttpOnly, Secure, and SameSite set

@security
Scenario: Password reset token cannot be reused
  Given a user has completed a password reset with a valid token
  When the same reset token is submitted again
  Then the request is rejected as invalid
```
