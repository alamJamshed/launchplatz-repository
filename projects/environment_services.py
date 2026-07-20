import errno
import socket
import uuid

import paramiko
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.utils import timezone

from servers.services import ServerCredentialCipher, SSHKeyParser


class EnvironmentCredentialCipher:
    @staticmethod
    def _fernet():
        key = getattr(settings, 'ENVIRONMENT_VARIABLE_ENCRYPTION_KEY', None)
        if not key:
            raise ImproperlyConfigured(
                'ENVIRONMENT_VARIABLE_ENCRYPTION_KEY must be configured.'
            )
        try:
            return Fernet(key.encode() if isinstance(key, str) else key)
        except (TypeError, ValueError) as exc:
            raise ImproperlyConfigured(
                'ENVIRONMENT_VARIABLE_ENCRYPTION_KEY must be a valid Fernet key.'
            ) from exc

    @classmethod
    def encrypt(cls, value):
        return cls._fernet().encrypt(value.encode()).decode()

    @classmethod
    def decrypt(cls, encrypted_value):
        try:
            return cls._fernet().decrypt(encrypted_value.encode()).decode()
        except InvalidToken as exc:
            raise EnvironmentOperationError(
                'credential_error', 'An environment value could not be decrypted.', 400
            ) from exc


class EnvironmentOperationError(Exception):
    def __init__(self, category, message, status_code=502):
        super().__init__(message)
        self.category = category
        self.message = message
        self.status_code = status_code


def quote_dotenv_value(value):
    escaped = (
        value.replace('\\', '\\\\')
        .replace('"', '\\"')
        .replace('$', '\\$')
        .replace('\r', '\\r')
        .replace('\n', '\\n')
    )
    return f'"{escaped}"'


def serialize_dotenv(variables):
    lines = [
        f'{variable.key}={quote_dotenv_value(EnvironmentCredentialCipher.decrypt(variable.encrypted_value))}'
        for variable in sorted(variables, key=lambda item: item.key)
    ]
    return ('\n'.join(lines) + ('\n' if lines else '')).encode()


class RemoteEnvironmentService:
    def __init__(self, project):
        self.project = project
        self.client = None
        self.sftp = None
        self.home = None
        self.workspace = None

    def __enter__(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        server = self.project.server
        try:
            server_key = SSHKeyParser.parse(
                ServerCredentialCipher.decrypt(server.encrypted_private_key)
            )
            timeout = getattr(settings, 'SSH_CONNECTION_TIMEOUT', 30)
            self.client.connect(
                hostname=str(server.ip_address), port=server.ssh_port,
                username=server.username, pkey=server_key, timeout=timeout,
                banner_timeout=timeout, auth_timeout=timeout,
                look_for_keys=False, allow_agent=False,
            )
            self.sftp = self.client.open_sftp()
            self.home = self.sftp.normalize('.')
            self.workspace = f'{self.home}/launchplatz/projects/{self.project.pk}'
            self._require_workspace()
            return self
        except EnvironmentOperationError:
            self.__exit__(None, None, None)
            raise
        except (ValidationError, ImproperlyConfigured) as exc:
            self.__exit__(None, None, None)
            raise EnvironmentOperationError(
                'credential_error', 'A stored SSH credential is invalid.', 400
            ) from exc
        except paramiko.AuthenticationException as exc:
            self.__exit__(None, None, None)
            raise EnvironmentOperationError(
                'ssh_authentication_failed', 'VPS SSH authentication failed.'
            ) from exc
        except (socket.timeout, TimeoutError) as exc:
            self.__exit__(None, None, None)
            raise EnvironmentOperationError(
                'timeout', 'VPS SSH connection timed out.', 504
            ) from exc
        except (paramiko.SSHException, OSError) as exc:
            self.__exit__(None, None, None)
            raise EnvironmentOperationError(
                'ssh_error', 'Could not connect to the VPS.'
            ) from exc

    def __exit__(self, exc_type, exc_value, traceback):
        if self.sftp:
            self.sftp.close()
        if self.client:
            self.client.close()

    def _require_workspace(self):
        try:
            self.sftp.stat(f'{self.workspace}/.git')
        except OSError as exc:
            if getattr(exc, 'errno', None) in {None, errno.ENOENT, 2}:
                raise EnvironmentOperationError(
                    'repository_not_cloned', 'Repository has not been cloned.', 409
                ) from exc
            raise

    def generate(self, variables):
        content = serialize_dotenv(variables)
        destination = f'{self.workspace}/.env'
        temporary = f'{destination}.tmp-{uuid.uuid4().hex}'
        try:
            with self.sftp.file(temporary, 'wb') as env_file:
                env_file.write(content)
                env_file.flush()
            self.sftp.chmod(temporary, 0o600)
            self.sftp.posix_rename(temporary, destination)
        except (OSError, paramiko.SSHException) as exc:
            try:
                self.sftp.remove(temporary)
            except OSError:
                pass
            raise EnvironmentOperationError(
                'filesystem_error', 'Could not write the remote environment file.'
            ) from exc
        return {
            'variable_count': len(variables),
            'generated_at': timezone.now(),
        }
