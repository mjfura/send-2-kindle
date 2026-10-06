from send_2_kindle import constants
from send_2_kindle.providers import GMAIL, ICLOUD, PROVIDERS, provider_for_host, provider_for_key


def test_known_hosts_map_to_providers() -> None:
    assert provider_for_host("smtp.gmail.com") is GMAIL
    assert provider_for_host("smtp.mail.me.com") is ICLOUD


def test_provider_for_host_ignores_case_and_spaces() -> None:
    assert provider_for_host("  SMTP.Mail.Me.com ") is ICLOUD


def test_unknown_host_has_no_provider() -> None:
    assert provider_for_host("smtp.example.com") is None


def test_provider_for_key() -> None:
    assert provider_for_key("icloud") is ICLOUD
    assert provider_for_key("other") is None


def test_provider_limits_are_below_amazons() -> None:
    for provider in PROVIDERS:
        assert provider.max_file_bytes < constants.MAX_EMAIL_SIZE_BYTES


def test_legacy_icloud_hosts_are_recognized() -> None:
    assert provider_for_host("smtp.me.com") is ICLOUD
    assert provider_for_host("smtp.mac.com") is ICLOUD
