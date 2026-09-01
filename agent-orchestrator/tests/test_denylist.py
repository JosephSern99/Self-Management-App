from denylist import is_denylisted

PROTECTED_EXAMPLES = [
    "app/Http/Controllers/PaymentController.php",
    "app/Http/Controllers/WebhookController.php",
    "config/cashier.php",
    "app/Models/User.php",
    "database/migrations/2014_10_12_000000_create_users_table.php",
    "app/Http/Controllers/Auth/AuthenticatedSessionController.php",
    "app/Http/Requests/Auth/LoginRequest.php",
    "app/Http/Middleware/Authenticate.php",
    "app/Http/Middleware/RedirectIfAuthenticated.php",
    "routes/auth.php",
    "config/auth.php",
    "config/sanctum.php",
    "app/Providers/AuthServiceProvider.php",
    "app/Http/Kernel.php",
    "bootstrap/app.php",
    "composer.json",
    "composer.lock",
    "package.json",
    "package-lock.json",
]

SAFE_EXAMPLES = [
    "app/Http/Controllers/FinanceController.php",
    "resources/views/finance/home.blade.php",
    "routes/web.php",
    "app/Services/FinanceEntityService.php",
    "app/Models/FinancialEntity.php",
]


def test_each_protected_example_is_denylisted():
    for path in PROTECTED_EXAMPLES:
        assert is_denylisted(path) is not None, f"{path} should be denylisted"


def test_each_safe_example_is_not_denylisted():
    for path in SAFE_EXAMPLES:
        assert is_denylisted(path) is None, f"{path} should NOT be denylisted"


def test_nested_migration_matches_glob():
    assert is_denylisted("database/migrations/nested/foo.php") is not None


def test_migrations_directory_itself_not_falsely_matched_as_sibling():
    # A file merely starting with the same prefix string, but not actually
    # inside database/migrations/, must not match.
    assert is_denylisted("database/migrations_backup/foo.php") is None


def test_windows_style_backslash_path_still_matches():
    assert is_denylisted("app\\Http\\Controllers\\PaymentController.php") is not None


def test_leading_slash_path_still_matches():
    assert is_denylisted("/app/Http/Controllers/PaymentController.php") is not None


def test_case_variant_still_matches():
    assert is_denylisted("app/http/controllers/paymentcontroller.php") is not None
    assert is_denylisted("CONFIG/CASHIER.PHP") is not None


def test_path_traversal_still_matches():
    # 4 "../" segments needed to walk back up to repo root from this depth.
    assert (
        is_denylisted("app/Http/Controllers/Auth/../../../../config/cashier.php")
        is not None
    )
    assert is_denylisted("./config/cashier.php") is not None


def test_repeated_slashes_still_match():
    assert is_denylisted("app//Http/Controllers//PaymentController.php") is not None


def test_trailing_slash_still_matches():
    assert is_denylisted("config/cashier.php/") is not None


def test_url_encoded_path_still_matches():
    assert is_denylisted("config%2Fcashier.php") is not None


def test_traversal_cannot_escape_to_falsely_match_unrelated_safe_file():
    # A traversal-normalized safe path must still read as safe -- over-
    # normalization shouldn't cause false positives either.
    assert is_denylisted("app/Http/Controllers/./FinanceController.php") is None
