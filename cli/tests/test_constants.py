from send_2_kindle import constants


def test_allowed_extensions_are_lowercase_with_leading_dot() -> None:
    for extension in constants.ALLOWED_EXTENSIONS:
        assert extension.startswith(".")
        assert extension == extension.lower()


def test_allowed_extensions_match_amazon_list() -> None:
    expected = {
        ".doc", ".docx", ".html", ".htm", ".rtf", ".txt",
        ".jpeg", ".jpg", ".gif", ".png", ".bmp", ".pdf", ".epub",
    }  # fmt: skip
    assert expected == constants.ALLOWED_EXTENSIONS


def test_mobi_is_not_allowed() -> None:
    assert ".mobi" not in constants.ALLOWED_EXTENSIONS


def test_limits() -> None:
    assert constants.MAX_EMAIL_SIZE_BYTES == 50_000_000
    assert constants.SMTP_TIMEOUT_SECONDS == 30.0
