"""Single source of truth for protected paths the agent must never touch
(Architecture AD-7, realizes FR-5). Checked by both Locate and Push
(Story 1.7) -- they import this module rather than maintaining separate
lists, so the two enforcement points can't drift apart.

This is the only safety mechanism standing between an unattended agent and
a live production app's payment/auth code, given there is no human review
gate before a push. Matching is deliberately conservative: normalized,
case-insensitive, and traversal-proof, so it fails toward over-blocking
rather than a bypass.

Patterns are investigated from the real repo, not guessed:
- Payments: PaymentController/WebhookController handle Stripe/Cashier;
  config/cashier.php is Cashier's config; app/Models/User.php carries the
  Billable trait (editing it can alter billing behavior without touching
  either of the above).
- Auth: the Auth-prefixed controller/request paths, the two auth-related
  middleware classes, routes/auth.php, config/auth.php (guards/providers),
  config/sanctum.php, app/Providers/AuthServiceProvider.php, and
  app/Http/Kernel.php (registers middleware globally -- editing it can
  neuter auth checks without touching any of the above).
- Schema: database/migrations covers all schema changes.
- Supply chain: dependency manifests. An agent that can edit these can
  swap a dependency with no review gate to catch it -- same blast-radius
  class as the above, so protected the same way.
"""

import posixpath
import urllib.parse

PROTECTED_PATH_PATTERNS = [
    # Payments
    "app/Http/Controllers/PaymentController.php",
    "app/Http/Controllers/WebhookController.php",
    "config/cashier.php",
    "app/Models/User.php",
    # Auth
    "app/Http/Controllers/Auth/**",
    "app/Http/Requests/Auth/**",
    "app/Http/Middleware/Authenticate.php",
    "app/Http/Middleware/RedirectIfAuthenticated.php",
    "routes/auth.php",
    "config/auth.php",
    "config/sanctum.php",
    "app/Providers/AuthServiceProvider.php",
    "app/Http/Kernel.php",
    "bootstrap/app.php",
    # Schema
    "database/migrations/**",
    # Supply chain
    "composer.json",
    "composer.lock",
    "package.json",
    "package-lock.json",
]

_NORMALIZED_LITERAL_PATTERNS = frozenset(
    p.lower() for p in PROTECTED_PATH_PATTERNS if not p.endswith("/**")
)
_NORMALIZED_GLOB_PREFIXES = tuple(
    p[: -len("/**")].lower() for p in PROTECTED_PATH_PATTERNS if p.endswith("/**")
)


class ScopeViolation(RuntimeError):
    pass


def _normalize(path: str) -> str:
    path = urllib.parse.unquote(path)
    path = path.replace("\\", "/")
    path = posixpath.normpath(path).lstrip("/")
    return path.lower()


def is_denylisted(path: str) -> str | None:
    """Returns the matching pattern if `path` is protected, else None.
    Case-insensitive, traversal-resolved, separator-normalized -- matching
    is intentionally conservative (over-blocking is safe; under-blocking
    is not)."""
    normalized = _normalize(path)

    if normalized in _NORMALIZED_LITERAL_PATTERNS:
        for pattern in PROTECTED_PATH_PATTERNS:
            if not pattern.endswith("/**") and pattern.lower() == normalized:
                return pattern

    for i, prefix in enumerate(_NORMALIZED_GLOB_PREFIXES):
        if normalized == prefix or normalized.startswith(prefix + "/"):
            return [p for p in PROTECTED_PATH_PATTERNS if p.endswith("/**")][i]

    return None
