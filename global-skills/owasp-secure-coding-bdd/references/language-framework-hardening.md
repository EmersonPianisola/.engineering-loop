# Language & Framework Hardening (beyond Node/Django/Rails/mobile)

Companion to `platform-framework-specific.md`, which covers Node.js, Django, Ruby on Rails,
and mobile in depth. This file covers the remaining language/framework-specific OWASP
cheat sheets. Read the section matching the stack you're writing in — apply it in addition
to the general controls (injection, access control, crypto, etc.), not instead of them.

## Java
Covers: Java Security, Injection Prevention in Java, Bean Validation, JAAS.
- Injection: `PreparedStatement` for SQL; `ProcessBuilder` with argument arrays (never a
  shell string); parameterized JPA; OWASP Java Encoder for output.
- Deserialization: never native-deserialize untrusted data; use allow-list
  `ObjectInputFilter`; prefer data-only formats + schema.
- XML: disable DTDs/external entities on every parser (see XXE reference).
- Bean Validation (JSR-380): annotate DTOs (`@NotNull`, `@Size`, `@Pattern`, `@Email`);
  validate at the boundary; write custom validators for domain rules.
- JAAS: use standard login modules and role checks; don't hand-roll auth where the
  framework provides it; verify principals server-side.
- Crypto via JCA only; no home-grown algorithms.

## .NET / C#
Covers: DotNet Security.
- SQL via parameterized ADO.NET / EF Core (no string interpolation into queries).
- Antiforgery tokens on state-changing requests; `[ValidateAntiForgeryToken]`.
- Cookies `HttpOnly` + `Secure` + `SameSite`; auth cookies via the framework.
- Secrets via the Data Protection API / a secret manager, not `appsettings.json` in repo.
- Disable detailed errors in production (`customErrors`/`DeveloperExceptionPage` off).
- Output encoding via Razor (on by default); `HtmlEncoder`/`JavaScriptEncoder` for manual.

## PHP (config + frameworks)
Covers: PHP Configuration, Laravel, Symfony.
- `php.ini` hardening: `display_errors=Off`, `expose_php=Off`, `disable_functions` for
  dangerous calls, `open_basedir`, secure `session.cookie_*` flags.
- Laravel: Eloquent parameter binding; `$fillable`/`$guarded` to prevent mass assignment;
  CSRF middleware on; validation rules in Form Requests; `.env` out of version control.
- Symfony: security voters for authz; Doctrine parameterized queries; CSRF on forms; Twig
  auto-escaping (on by default); secrets vault.

## C / C++
Covers: C-Based Toolchain Hardening.
- Compile with hardening: `-fstack-protector-strong`, `-D_FORTIFY_SOURCE=2`, `-fPIE -pie`,
  full RELRO (`-Wl,-z,relro,-z,now`), `-Wformat -Wformat-security`.
- Treat warnings as errors; run ASan/UBSan (and fuzzing) in CI.
- Avoid unsafe functions (`strcpy`, `sprintf`, `gets`); use bounded equivalents.

## Browser extensions
Covers: Browser Extension Vulnerabilities.
- Request minimal permissions in the manifest; avoid broad host permissions.
- Strict CSP in the manifest; no remote code execution / no `eval`.
- Validate messages passed between content scripts and background/service worker.
- Sanitize any DOM injection into pages; treat page content as untrusted.

## @security BDD scenario patterns
```gherkin
  @security
  Scenario: Java endpoint rejects mass-assignment of protected fields
    Given a request body includes "role": "ADMIN"
    When the object is bound from the request
    Then the role field is ignored and defaults to the caller's actual role

  @security
  Scenario: .NET form rejects a request without a valid antiforgery token
    Given a state-changing POST request without a valid antiforgery token
    When the request is processed
    Then it is rejected with an antiforgery validation failure

  @security
  Scenario: PHP application does not expose stack traces in production
    Given the application runs with production configuration
    When an unhandled error occurs
    Then the client receives a generic error and no PHP stack trace or file path
```
