import os
import socket
import subprocess
import sys
import time


def wait_for_service(host, port, label, attempts=30, delay=1):
    for _ in range(attempts):
        try:
            with socket.create_connection((host, port), timeout=2):
                return
        except OSError:
            time.sleep(delay)
    raise RuntimeError(f'{label} did not become available at {host}:{port}.')


def main():
    role = sys.argv[1] if len(sys.argv) > 1 else 'web'
    wait_for_service(os.environ.get('DB_HOST', 'db'), int(os.environ.get('DB_PORT', 5432)), 'PostgreSQL')
    wait_for_service('redis', 6379, 'Redis')

    if role == 'web':
        subprocess.run(
            [sys.executable, 'manage.py', 'migrate', '--noinput'], check=True
        )
        command = [sys.executable, 'manage.py', 'runserver', '0.0.0.0:8000']
    elif role == 'worker':
        command = ['celery', '-A', 'Config', 'worker', '--loglevel=info']
    else:
        command = sys.argv[1:]

    os.execvp(command[0], command)


if __name__ == '__main__':
    main()
