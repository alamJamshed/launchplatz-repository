import io

import paramiko


def generate_private_key():
    key = paramiko.RSAKey.generate(1024)
    output = io.StringIO()
    key.write_private_key(output)
    return output.getvalue()
