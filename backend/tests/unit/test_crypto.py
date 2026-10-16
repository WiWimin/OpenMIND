from app.core.crypto import decrypt, encrypt


def test_encrypt_decrypt_roundtrip() -> None:
    secret = "sk-test-1234567890"
    token = encrypt(secret)
    assert token != secret
    assert "sk-test" not in token
    assert decrypt(token) == secret


def test_encrypt_is_nondeterministic() -> None:
    assert encrypt("same-secret") != encrypt("same-secret")


def test_decrypt_preserves_unicode() -> None:
    value = "密钥-测试-🔐"
    assert decrypt(encrypt(value)) == value
