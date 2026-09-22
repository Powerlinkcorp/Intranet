import paramiko

def ssh_command(host, user, password, command):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, username=user, password=password)
    stdin, stdout, stderr = client.exec_command(command)
    return stdout.read().decode('utf-8')

print(ssh_command('10.0.1.179', 'root', 'Redes2010', 'systemctl list-units --type=service | grep -i uvicorn'))
print("=== INTRANET ===")
print(ssh_command('10.0.1.179', 'root', 'Redes2010', 'systemctl list-units --type=service | grep -i intranet'))
