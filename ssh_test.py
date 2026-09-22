import paramiko
import time

def ssh_command(host, user, password, command):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, username=user, password=password)
    
    stdin, stdout, stderr = client.exec_command(command)
    out = stdout.read().decode('utf-8')
    err = stderr.read().decode('utf-8')
    
    client.close()
    return out, err

out, err = ssh_command('10.0.1.179', 'root', 'Redes2010', 'journalctl -u uvicorn -n 100 --no-pager')
print("STDOUT:")
print(out)
print("STDERR:")
print(err)
