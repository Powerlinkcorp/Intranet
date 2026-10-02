import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.0.1.179', username='root', password='Redes2010')
stdin, stdout, stderr = ssh.exec_command("curl -s -X GET http://127.0.0.1:8001/login | head -n 5")
print(stdout.read().decode())
