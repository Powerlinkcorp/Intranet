import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.0.1.179', username='root', password='Redes2010')

stdin, stdout, stderr = ssh.exec_command('grep DATABASE_URL /var/www/intranet_qa/.env')
print("QA .env:\n" + stdout.read().decode())

stdin, stdout, stderr = ssh.exec_command('grep SQLITE /var/www/intranet_qa/.env')
print("QA .env SQLITE:\n" + stdout.read().decode())
