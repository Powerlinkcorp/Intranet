import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.0.1.179', username='root', password='Redes2010')
stdin, stdout, stderr = ssh.exec_command("cd /var/www/intranet_qa && git ls-files | grep .env")
print("TRACKED:", stdout.read().decode())
