"""
Utility for encrypting and decrypting customer photos using Fernet symmetric encryption.

Photos are encrypted at rest and decrypted when served to authorized users.
The encryption key is stored in settings via the CUSTOMER_PHOTO_ENCRYPTION_KEY env var.
"""

import base64
import io
import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    """Get a Fernet instance using the configured encryption key."""
    key = getattr(settings, "CUSTOMER_PHOTO_ENCRYPTION_KEY", None)
    if not key:
        raise ValueError(
            "CUSTOMER_PHOTO_ENCRYPTION_KEY is not configured in settings. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt_file(file_content: bytes) -> bytes:
    """Encrypt file content using Fernet."""
    fernet = _get_fernet()
    return fernet.encrypt(file_content)


def decrypt_file(encrypted_content: bytes) -> bytes:
    """Decrypt file content using Fernet."""
    fernet = _get_fernet()
    try:
        return fernet.decrypt(encrypted_content)
    except InvalidToken:
        logger.warning("Failed to decrypt file — may be unencrypted or corrupted.")
        # Return the original content if it can't be decrypted
        # (e.g., files uploaded before encryption was enabled)
        return encrypted_content


def encrypt_uploaded_file(uploaded_file) -> ContentFile:
    """
    Encrypt an uploaded file (InMemoryUploadedFile or similar) and return
    a new ContentFile with the encrypted content.
    """
    if uploaded_file is None:
        return None

    # Read the entire file content
    file_content = uploaded_file.read()
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)

    # Encrypt the content
    encrypted_content = encrypt_file(file_content)

    # Return a new ContentFile with the encrypted data
    # Preserve the original filename with .enc suffix
    name = getattr(uploaded_file, "name", "photo.enc")
    if not name.endswith(".enc"):
        name = name + ".enc"

    return ContentFile(encrypted_content, name=name)


def decrypt_photo_to_base64(file_field) -> str | None:
    """
    Read an encrypted photo from a FileField/ImageField, decrypt it,
    and return as a base64 data URI string.
    Returns None if the field is empty.
    """
    if not file_field or not file_field.name:
        return None

    try:
        file_field.open("rb")
        encrypted_content = file_field.read()
        file_field.close()

        decrypted_content = decrypt_file(encrypted_content)

        # Detect content type from the original filename
        original_name = file_field.name.replace(".enc", "")
        if original_name.lower().endswith(".png"):
            content_type = "image/png"
        elif original_name.lower().endswith((".jpg", ".jpeg")):
            content_type = "image/jpeg"
        elif original_name.lower().endswith(".gif"):
            content_type = "image/gif"
        elif original_name.lower().endswith(".webp"):
            content_type = "image/webp"
        else:
            content_type = "image/jpeg"

        b64 = base64.b64encode(decrypted_content).decode("utf-8")
        return f"data:{content_type};base64,{b64}"
    except Exception as e:
        logger.error("Failed to decrypt photo %s: %s", file_field.name, e)
        return None
