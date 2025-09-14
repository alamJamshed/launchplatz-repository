from django.core.mail import get_connection
from django.conf import settings
from cryptography.fernet import Fernet
from utility.models import SMTPSettings
import base64
import logging

logger = logging.getLogger(__name__)


class SMTPConfigManager:
    """Dynamic SMTP configuration manager"""
    
    @staticmethod
    def get_encryption_key():
        """Get or create encryption key for SMTP passwords"""
        key = getattr(settings, 'SMTP_ENCRYPTION_KEY', None)
        if not key:
            # Generate a new key if not exists
            key = Fernet.generate_key()
            logger.warning("SMTP_ENCRYPTION_KEY not found in settings. Using generated key.")
        return key
    
    @staticmethod
    def encrypt_password(password):
        """Encrypt SMTP password"""
        if not password:
            return password
        key = SMTPConfigManager.get_encryption_key()
        f = Fernet(key)
        encrypted = f.encrypt(password.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    @staticmethod
    def decrypt_password(encrypted_password):
        """Decrypt SMTP password"""
        if not encrypted_password:
            return encrypted_password
        try:
            key = SMTPConfigManager.get_encryption_key()
            f = Fernet(key)
            decoded = base64.urlsafe_b64decode(encrypted_password.encode())
            return f.decrypt(decoded).decode()
        except Exception as e:
            logger.error(f"Failed to decrypt SMTP password: {e}")
            return encrypted_password
    
    @staticmethod
    def get_active_smtp_settings():
        """Get active SMTP settings from database"""
        try:
            return SMTPSettings.objects.filter(is_active=True).first()
        except Exception:
            return None
    
    @staticmethod
    def get_smtp_connection():
        """Get SMTP connection with dynamic settings"""
        smtp_settings = SMTPConfigManager.get_active_smtp_settings()
        
        if smtp_settings:
            try:
                decrypted_password = SMTPConfigManager.decrypt_password(smtp_settings.password)
                
                connection = get_connection(
                    backend='django.core.mail.backends.smtp.EmailBackend',
                    host=smtp_settings.host,
                    port=smtp_settings.port,
                    username=smtp_settings.username,
                    password=decrypted_password,
                    use_tls=smtp_settings.use_tls,
                    use_ssl=smtp_settings.use_ssl,
                )
                return connection, smtp_settings.from_email
            except Exception as e:
                logger.error(f"Failed to create SMTP connection: {e}")
        
        # Fallback
        return None, 'noreply@example.com'
    
    @staticmethod
    def create_default_smtp_settings():
        """Create default SMTP settings if none exist"""
        if not SMTPSettings.objects.exists():
            SMTPSettings.objects.create(
                host='smtp.gmail.com',
                port=587,
                username='',
                password='',
                use_tls=True,
                use_ssl=False,
                from_email='noreply@example.com',
                from_name='Django Base 2025',
                is_active=False  # Inactive until configured
            )
            logger.info("Default SMTP settings created (inactive)")