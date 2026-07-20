import re
import shlex
import socket
from dataclasses import dataclass

import paramiko
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError

from servers.services import ServerCredentialCipher, SSHKeyParser


ANSI_ESCAPE = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
BRANCH_PATTERN = re.compile(r'^(?![./])(?!.*\.\.)(?!.*[~^:?*\[\\\s])[A-Za-z0-9._/-]+$')


def sanitize_git_output(value, limit=20000):
    value = ANSI_ESCAPE.sub('', value or '').replace('\x00', '')
    return value[-limit:]


class GitCredentialCipher:
    @staticmethod
    def _fernet():
        key = getattr(settings, 'GIT_CREDENTIAL_ENCRYPTION_KEY', None)
        if not key:
            raise ImproperlyConfigured(
                'GIT_CREDENTIAL_ENCRYPTION_KEY must be configured.'
            )
        try:
            return Fernet(key.encode() if isinstance(key, str) else key)
        except (TypeError, ValueError) as exc:
            raise ImproperlyConfigured(
                'GIT_CREDENTIAL_ENCRYPTION_KEY must be a valid Fernet key.'
            ) from exc

    @classmethod
    def encrypt(cls, private_key):
        return cls._fernet().encrypt(private_key.encode()).decode()

    @classmethod
    def decrypt(cls, encrypted_private_key):
        try:
            return cls._fernet().decrypt(encrypted_private_key.encode()).decode()
        except InvalidToken as exc:
            raise GitOperationError(
                'credential_error', 'Git credential could not be decrypted.', 400
            ) from exc


class GitOperationError(Exception):
    def __init__(self, category, message, status_code=502, output=''):
        super().__init__(message)
        self.category = category
        self.message = message
        self.status_code = status_code
        self.output = sanitize_git_output(output)


@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def output(self):
        return sanitize_git_output('\n'.join(filter(None, [self.stdout, self.stderr])))


class RemoteGitService:
    def __init__(self, project):
        self.project = project
        self.client = None
        self.sftp = None
        self.home = None
        self.workspace = None
        self.git_key_path = None
        self.known_hosts_path = None

    @staticmethod
    def validate_branch(branch):
        if not branch or len(branch) > 255 or not BRANCH_PATTERN.fullmatch(branch):
            raise GitOperationError(
                'invalid_branch', 'Enter a valid Git branch name.', 400
            )
        if branch.endswith(('/', '.', '.lock')):
            raise GitOperationError(
                'invalid_branch', 'Enter a valid Git branch name.', 400
            )
        return branch

    @staticmethod
    def parse_branches(output):
        branches = []
        for line in output.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1].startswith('refs/heads/'):
                branches.append(parts[1].removeprefix('refs/heads/'))
        return sorted(set(branches))

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
                hostname=str(server.ip_address),
                port=server.ssh_port,
                username=server.username,
                pkey=server_key,
                timeout=timeout,
                banner_timeout=timeout,
                auth_timeout=timeout,
                look_for_keys=False,
                allow_agent=False,
            )
            self.sftp = self.client.open_sftp()
            self.home = self.sftp.normalize('.')
            self.workspace = f'{self.home}/launchplatz/projects/{self.project.pk}'
            self.git_key_path = f'{self.home}/.launchplatz/keys/project-{self.project.pk}'
            self.known_hosts_path = f'{self.home}/.launchplatz/known_hosts'
            self._run('git --version', category='git_not_installed')
            self._prepare_git_credential()
            return self
        except GitOperationError:
            self.__exit__(None, None, None)
            raise
        except (ValidationError, ImproperlyConfigured) as exc:
            self.__exit__(None, None, None)
            raise GitOperationError(
                'credential_error', 'A stored SSH credential is invalid.', 400
            ) from exc
        except paramiko.AuthenticationException as exc:
            self.__exit__(None, None, None)
            raise GitOperationError(
                'ssh_authentication_failed', 'VPS SSH authentication failed.'
            ) from exc
        except (socket.timeout, TimeoutError) as exc:
            self.__exit__(None, None, None)
            raise GitOperationError('timeout', 'VPS SSH connection timed out.', 504) from exc
        except (paramiko.SSHException, OSError) as exc:
            self.__exit__(None, None, None)
            raise GitOperationError('ssh_error', 'Could not connect to the VPS.') from exc

    def __exit__(self, exc_type, exc_value, traceback):
        if self.sftp:
            self.sftp.close()
        if self.client:
            self.client.close()

    def _run_raw(self, command):
        timeout = getattr(settings, 'GIT_OPERATION_TIMEOUT', 120)
        try:
            _, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            stdout.channel.set_combine_stderr(True)
            output = stdout.read().decode(errors='replace')
            exit_code = stdout.channel.recv_exit_status()
            return CommandResult(
                exit_code,
                output,
                '',
            )
        except (socket.timeout, TimeoutError) as exc:
            raise GitOperationError(
                'timeout', 'Git operation timed out.', 504
            ) from exc

    def _run(self, command, category='git_error'):
        result = self._run_raw(command)
        if result.exit_code != 0:
            message = (
                'Git is not installed on the VPS.'
                if category == 'git_not_installed'
                else 'Remote Git command failed.'
            )
            raise GitOperationError(category, message, 502, result.output)
        return result

    def _prepare_git_credential(self):
        self._run(
            f'mkdir -p {shlex.quote(self.home + "/.launchplatz/keys")} '
            f'{shlex.quote(self.home + "/launchplatz/projects")} && '
            f'chmod 700 {shlex.quote(self.home + "/.launchplatz")} '
            f'{shlex.quote(self.home + "/.launchplatz/keys")}'
        )
        if not self._uses_ssh_repository():
            return
        if not self.project.encrypted_git_private_key:
            raise GitOperationError(
                'credential_error',
                'An SSH Git private key is required for this repository.',
                400,
            )
        private_key = GitCredentialCipher.decrypt(
            self.project.encrypted_git_private_key
        )
        SSHKeyParser.parse(private_key)
        with self.sftp.file(self.git_key_path, 'wb') as key_file:
            key_file.write(private_key.encode())
        self.sftp.chmod(self.git_key_path, 0o600)

    def _uses_ssh_repository(self):
        url = self.project.git_repository_url
        return url.startswith('ssh://') or re.match(r'^[^@]+@[^:]+:', url)

    def _git_environment(self):
        if not self._uses_ssh_repository():
            return ''
        ssh_command = (
            f'ssh -i {shlex.quote(self.git_key_path)} -o IdentitiesOnly=yes '
            f'-o StrictHostKeyChecking=accept-new '
            f'-o UserKnownHostsFile={shlex.quote(self.known_hosts_path)}'
        )
        return f'GIT_SSH_COMMAND={shlex.quote(ssh_command)} '

    def _require_clone(self):
        result = self._run_raw(
            f'test -d {shlex.quote(self.workspace + "/.git")}'
        )
        if result.exit_code != 0:
            raise GitOperationError(
                'repository_not_cloned', 'Repository has not been cloned.', 409
            )

    def _state(self):
        commit = self._run(
            f'git -C {shlex.quote(self.workspace)} rev-parse HEAD'
        ).stdout.strip()
        branch = self._run(
            f'git -C {shlex.quote(self.workspace)} branch --show-current'
        ).stdout.strip()
        return branch, commit

    def clone(self, user=None):
        exists = self._run_raw(f'test -e {shlex.quote(self.workspace)}')
        if exists.exit_code == 0:
            raise GitOperationError(
                'repository_already_cloned', 'Project workspace already exists.', 409
            )
        branch = self.validate_branch(self.project.branch)
        result = self._run(
            f'{self._git_environment()}git clone --single-branch '
            f'--branch {shlex.quote(branch)} '
            f'{shlex.quote(self.project.git_repository_url)} '
            f'{shlex.quote(self.workspace)}'
        )
        current_branch, commit = self._state()
        self.project.record_git_state(current_branch, commit, cloned=True, user=user)
        return {
            'branch': current_branch, 'commit': commit,
            'workspace': f'~/launchplatz/projects/{self.project.pk}',
            '_output': result.output,
        }

    def pull(self, user=None):
        self._require_clone()
        dirty = self._run(
            f'git -C {shlex.quote(self.workspace)} status --porcelain'
        ).stdout.strip()
        if dirty:
            raise GitOperationError(
                'working_tree_dirty', 'Working tree contains local changes.', 409
            )
        branch = self.validate_branch(self.project.branch)
        current_branch = self._run(
            f'git -C {shlex.quote(self.workspace)} branch --show-current'
        ).stdout.strip()
        if current_branch != branch:
            raise GitOperationError(
                'branch_mismatch',
                'Working tree branch does not match the selected Project branch.',
                409,
            )
        result = self._run(
            f'{self._git_environment()}git -C {shlex.quote(self.workspace)} '
            f'pull --ff-only origin {shlex.quote(branch)}'
        )
        current_branch, commit = self._state()
        self.project.record_git_state(current_branch, commit, user=user)
        return {'branch': current_branch, 'commit': commit, '_output': result.output}

    def current_commit(self, user=None):
        self._require_clone()
        branch, commit = self._state()
        self.project.record_git_state(branch, commit, user=user)
        return {'branch': branch, 'commit': commit, '_output': ''}

    def branches(self):
        self._require_clone()
        result = self._run(
            f'{self._git_environment()}git -C {shlex.quote(self.workspace)} '
            'ls-remote --heads origin'
        )
        return {'branches': self.parse_branches(result.stdout), '_output': result.output}

    def select_branch(self, branch, user=None):
        self._require_clone()
        branch = self.validate_branch(branch)
        dirty = self._run(
            f'git -C {shlex.quote(self.workspace)} status --porcelain'
        ).stdout.strip()
        if dirty:
            raise GitOperationError(
                'working_tree_dirty', 'Working tree contains local changes.', 409
            )
        self._run(
            f'{self._git_environment()}git -C {shlex.quote(self.workspace)} '
            f'fetch origin {shlex.quote(branch)}'
        )
        local_ref = shlex.quote(f'refs/heads/{branch}')
        command = (
            f'if git -C {shlex.quote(self.workspace)} show-ref --verify --quiet {local_ref}; '
            f'then git -C {shlex.quote(self.workspace)} checkout {shlex.quote(branch)}; '
            f'else git -C {shlex.quote(self.workspace)} checkout -b {shlex.quote(branch)} '
            f'--track {shlex.quote("origin/" + branch)}; fi && '
            f'git -C {shlex.quote(self.workspace)} merge --ff-only '
            f'{shlex.quote("origin/" + branch)}'
        )
        result = self._run(command)
        current_branch, commit = self._state()
        self.project.branch = current_branch
        self.project.save(update_fields=['branch'])
        self.project.record_git_state(current_branch, commit, user=user)
        return {'branch': current_branch, 'commit': commit, '_output': result.output}
