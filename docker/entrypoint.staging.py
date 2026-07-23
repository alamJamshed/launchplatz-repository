import os
import socket
import subprocess
import sys
import time


def wait_for(host, port, label, attempts=60):
    for _ in range(attempts):
        try:
            with socket.create_connection((host, port), timeout=2):
                return
        except OSError:
            time.sleep(1)
    raise RuntimeError(f'{label} did not become available.')


def main():
    role = sys.argv[1] if len(sys.argv) > 1 else 'web'
    wait_for(os.environ.get('DB_HOST', 'db'), 5432, 'PostgreSQL')
    wait_for('redis', 6379, 'Redis')
    if role == 'web':
        subprocess.run([sys.executable, 'manage.py', 'migrate', '--noinput'], check=True)
        subprocess.run([sys.executable, 'manage.py', 'collectstatic', '--noinput'], check=True)
        command = [
            'gunicorn', 'Config.wsgi:application', '--bind', '0.0.0.0:8000',
            '--workers', os.environ.get('GUNICORN_WORKERS', '3'),
            '--timeout', os.environ.get('GUNICORN_TIMEOUT', '120'),
            '--access-logfile', '-', '--error-logfile', '-',
        ]
    elif role == 'worker':
        command = ['celery', '-A', 'Config', 'worker', '--loglevel=info']
    else:
        command = sys.argv[1:]
    os.execvp(command[0], command)


if __name__ == '__main__':
    main()
