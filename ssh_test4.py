import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')

def ssh_command(host, user, password, command):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, username=user, password=password)
    stdin, stdout, stderr = client.exec_command(command)
    return stdout.read().decode('utf-8')

print(ssh_command('10.0.1.179', 'root', 'Redes2010', 'journalctl -u intranet_qa.service -n 100 --no-pager'))
