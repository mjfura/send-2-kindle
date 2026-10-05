import pytest

from send_2_kindle import errors


@pytest.mark.parametrize(
    "error_class",
    [
        errors.ConfigError,
        errors.FileValidationError,
        errors.SmtpConnectionError,
        errors.SmtpAuthError,
        errors.SendError,
    ],
)
def test_every_error_is_an_s2k_error(error_class: type[Exception]) -> None:
    assert issubclass(error_class, errors.S2KError)
