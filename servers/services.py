import io
import socket
from time import perf_counter

import paramiko
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.utils import timezone


class SSHKeyPairGenerator:
    @staticmethod
    def generate():
        key = ed25519.Ed25519PrivateKey.generate()
        private_key = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.OpenSSH,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()
        public_key = key.public_key().public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH,
        ).decode()
        return private_key, f'{public_key} launchplatz'


class ServerCredentialCipher:
    @staticmethod
    def _fernet():
        key = getattr(settings, 'SERVER_CREDENTIAL_ENCRYPTION_KEY', None)
        if not key:
            raise ImproperlyConfigured(
                'SERVER_CREDENTIAL_ENCRYPTION_KEY must be configured.'
            )
        try:
            return Fernet(key.encode() if isinstance(key, str) else key)
        except (TypeError, ValueError) as exc:
            raise ImproperlyConfigured(
                'SERVER_CREDENTIAL_ENCRYPTION_KEY must be a valid Fernet key.'
            ) from exc

    @classmethod
    def encrypt(cls, private_key):
        return cls._fernet().encrypt(private_key.encode()).decode()

    @classmethod
    def decrypt(cls, encrypted_private_key):
        try:
            return cls._fernet().decrypt(encrypted_private_key.encode()).decode()
        except InvalidToken as exc:
            raise ValidationError('Stored server credential could not be decrypted.') from exc


class SSHKeyParser:
    KEY_CLASSES = (
        paramiko.RSAKey,
        paramiko.ECDSAKey,
        paramiko.Ed25519Key,
    )

    @classmethod
    def parse(cls, private_key):
        if not private_key or not private_key.strip():
            raise ValidationError('Private key is required.')

        password_protected = False
        for key_class in cls.KEY_CLASSES:
            try:
                return key_class.from_private_key(io.StringIO(private_key))
            except paramiko.PasswordRequiredException:
                password_protected = True
            except (paramiko.SSHException, ValueError):
                continue

        if password_protected:
            raise ValidationError('Password-protected private keys are not supported.')
        raise ValidationError('Private key must be a valid RSA, ECDSA, or Ed25519 key.')


class SSHConnectionTester:
    @staticmethod
    def _offline(reason):
        return {
            'status': 'Offline',
            'reason': reason,
            'checked_at': timezone.now(),
        }

    @classmethod
    def test(cls, server):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        started_at = perf_counter()

        try:
            private_key = ServerCredentialCipher.decrypt(
                server.encrypted_private_key
            )
            parsed_key = SSHKeyParser.parse(private_key)
            timeout = getattr(settings, 'SSH_CONNECTION_TIMEOUT', 30)
            client.connect(
                hostname=str(server.ip_address),
                port=server.ssh_port,
                username=server.username,
                pkey=parsed_key,
                timeout=timeout,
                banner_timeout=timeout,
                auth_timeout=timeout,
                look_for_keys=False,
                allow_agent=False,
            )
            return {
                'status': 'Online',
                'latency_ms': round((perf_counter() - started_at) * 1000, 2),
                'checked_at': timezone.now(),
            }
        except paramiko.AuthenticationException:
            return cls._offline('authentication_failed')
        except (socket.timeout, TimeoutError):
            return cls._offline('timeout')
        except (paramiko.ssh_exception.NoValidConnectionsError, OSError):
            return cls._offline('host_unreachable')
        except (ValidationError, ImproperlyConfigured):
            return cls._offline('credential_error')
        except paramiko.SSHException:
            return cls._offline('ssh_error')
        finally:
            client.close()
