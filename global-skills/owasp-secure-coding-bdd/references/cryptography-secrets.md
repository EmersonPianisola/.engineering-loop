# Cryptographic Storage, Key Management & Secrets

Covers: Cryptographic Storage, Key Management, Secrets Management, Transport Layer Security (TLS).

## Data at rest
- Encrypt sensitive data at rest (PII, financial data, health data, tokens) using a well-vetted authenticated encryption mode: **AES-256-GCM** (or ChaCha20-Poly1305). Never use unauthenticated modes like ECB or plain CBC without a MAC — they don't protect integrity and ECB leaks patterns.
- Never write custom cryptographic algorithms. Use vetted libraries (libsodium, platform crypto APIs like `crypto` in Node, `cryptography` in Python, BouncyCastle/JCA in Java, `System.Security.Cryptography` in .NET).
- Generate a unique random IV/nonce per encryption operation — never reuse an IV with the same key (catastrophic for GCM: it can leak the authentication key).
- Distinguish hashing from encryption: passwords are **hashed** (one-way, see authentication reference) never merely encrypted; data you need to read back later is **encrypted** (reversible with the key).

## Key management
- Never hard-code encryption keys, API keys, or credentials in source code, config files committed to version control, or client-side code/mobile apps.
- Store keys in a dedicated secrets manager (AWS KMS/Secrets Manager, GCP Secret Manager, Azure Key Vault, HashiCorp Vault) or, at minimum, environment variables injected at deploy time — never in the repo.
- Rotate keys periodically and support rotation without downtime (versioned keys, so old ciphertext can still be decrypted with the key version that produced it).
- Separate keys by purpose and environment (dev/staging/prod keys are distinct) so a leaked dev key can't decrypt production data.
- Restrict key access with least privilege (IAM policies scoping who/what can use a KMS key) and log key usage.

## Secrets in code and CI/CD
- Add `.env`, credential files, and key material to `.gitignore` before first commit — a secret committed to git history is compromised even if later removed (history must be scrubbed and the secret rotated, not just deleted going forward).
- Use CI/CD secret stores (GitHub Actions secrets, GitLab CI/CD variables marked protected+masked, etc.) rather than plaintext in pipeline config.
- Scan for accidentally committed secrets (gitleaks, truffleHog, or GitHub's built-in secret scanning) as a CI step.

## Transport security
- Enforce HTTPS/TLS for all traffic carrying credentials, tokens, or sensitive data — no plaintext HTTP fallback. Use HSTS (`Strict-Transport-Security` header) to prevent downgrade.
- Use TLS 1.2 minimum, prefer 1.3; disable legacy protocols (SSLv3, TLS 1.0/1.1) and weak cipher suites.
- Validate certificates properly in any code making outbound HTTPS calls — never disable certificate validation (`verify=False`, `rejectUnauthorized: false`) outside of a genuinely isolated local test environment, and never ship that disabled in production code paths.

## BDD security scenario patterns

```gherkin
@security
Scenario: Sensitive field is encrypted at rest
  Given a user record is saved with a national ID number
  When the raw database row is inspected
  Then the national ID field is not stored in plaintext

@security
Scenario: Application fails to start without required secrets configured
  Given the encryption key environment variable is not set
  When the application starts
  Then it fails fast with a clear configuration error
  And it does not fall back to a default or hardcoded key

@security
Scenario: All traffic is served over HTTPS with HSTS
  When a client requests the site over plain HTTP
  Then the server redirects to HTTPS
  And HTTPS responses include a Strict-Transport-Security header

@security
Scenario: Outbound HTTPS calls validate server certificates
  Given the application makes a request to an external API
  When the external API presents an invalid or self-signed certificate
  Then the request fails rather than proceeding with an unverified connection
```
