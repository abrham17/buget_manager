"""
Data Encryption Module for the Merchant Financial Agent

Provides secure encryption/decryption for sensitive financial data
using Fernet symmetric encryption with key rotation support.
"""

import os
import base64
import logging
from typing import Optional, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings

logger = logging.getLogger(__name__)


class EncryptionManager:
    """
    Manages data encryption and decryption for sensitive financial information
    
    Uses Fernet symmetric encryption with PBKDF2 key derivation for secure
    storage and transmission of sensitive data.
    """
    
    def __init__(self, password: Optional[str] = None, salt: Optional[bytes] = None):
        """
        Initialize encryption manager
        
        Args:
            password: Master password for key derivation (uses SECRET_KEY if not provided)
            salt: Salt for key derivation (generates random if not provided)
        """
        self.password = password or settings.SECRET_KEY
        self.salt = salt or self._generate_salt()
        self._fernet = None
        self._initialize_fernet()
    
    def _generate_salt(self) -> bytes:
        """Generate a random salt for key derivation"""
        return os.urandom(16)
    
    def _initialize_fernet(self):
        """Initialize Fernet encryption with derived key"""
        try:
            # Derive key from password using PBKDF2
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=self.salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(self.password.encode()))
            self._fernet = Fernet(key)
        except Exception as e:
            logger.error(f"Failed to initialize Fernet encryption: {e}")
            raise
    
    def encrypt(self, data: Union[str, bytes]) -> bytes:
        """
        Encrypt sensitive data
        
        Args:
            data: String or bytes to encrypt
            
        Returns:
            Encrypted bytes
        """
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            encrypted_data = self._fernet.encrypt(data)
            logger.debug("Data encrypted successfully")
            return encrypted_data
            
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise EncryptionError(f"Failed to encrypt data: {str(e)}")
    
    def decrypt(self, encrypted_data: bytes) -> str:
        """
        Decrypt sensitive data
        
        Args:
            encrypted_data: Encrypted bytes to decrypt
            
        Returns:
            Decrypted string
        """
        try:
            decrypted_data = self._fernet.decrypt(encrypted_data)
            logger.debug("Data decrypted successfully")
            return decrypted_data.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise EncryptionError(f"Failed to decrypt data: {str(e)}")
    
    def encrypt_field(self, value: str) -> str:
        """
        Encrypt a field value for database storage
        
        Args:
            value: String value to encrypt
            
        Returns:
            Base64 encoded encrypted string
        """
        if not value:
            return value
        
        try:
            encrypted = self.encrypt(value)
            return base64.urlsafe_b64encode(encrypted).decode('ascii')
        except Exception as e:
            logger.error(f"Field encryption failed: {e}")
            raise EncryptionError(f"Failed to encrypt field: {str(e)}")
    
    def decrypt_field(self, encrypted_value: str) -> str:
        """
        Decrypt a field value from database
        
        Args:
            encrypted_value: Base64 encoded encrypted string
            
        Returns:
            Decrypted string
        """
        if not encrypted_value:
            return encrypted_value
        
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_value.encode('ascii'))
            return self.decrypt(encrypted_bytes)
        except Exception as e:
            logger.error(f"Field decryption failed: {e}")
            raise EncryptionError(f"Failed to decrypt field: {str(e)}")
    
    def get_salt_hex(self) -> str:
        """Get salt as hexadecimal string for storage"""
        return self.salt.hex()
    
    @classmethod
    def from_salt_hex(cls, salt_hex: str, password: Optional[str] = None):
        """Create encryption manager from stored salt"""
        salt = bytes.fromhex(salt_hex)
        return cls(password=password, salt=salt)


class EncryptionError(Exception):
    """Custom exception for encryption-related errors"""
    pass


# Global encryption manager instance
def get_encryption_manager() -> EncryptionManager:
    """Get or create global encryption manager instance"""
    if not hasattr(settings, '_encryption_manager'):
        settings._encryption_manager = EncryptionManager()
    return settings._encryption_manager


def encrypt_sensitive_data(data: str) -> str:
    """Convenience function to encrypt sensitive data"""
    manager = get_encryption_manager()
    return manager.encrypt_field(data)


def decrypt_sensitive_data(encrypted_data: str) -> str:
    """Convenience function to decrypt sensitive data"""
    manager = get_encryption_manager()
    return manager.decrypt_field(encrypted_data)


# Example usage and testing
if __name__ == "__main__":
    # Test encryption/decryption
    manager = EncryptionManager()
    
    test_data = "Sensitive financial information: $1,000,000"
    print(f"Original: {test_data}")
    
    encrypted = manager.encrypt_field(test_data)
    print(f"Encrypted: {encrypted}")
    
    decrypted = manager.decrypt_field(encrypted)
    print(f"Decrypted: {decrypted}")
    
    print(f"Match: {test_data == decrypted}")
