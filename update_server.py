import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.0.1.179', username='root', password='Redes2010')

stdin, stdout, stderr = ssh.exec_command('cd /var/www/intranet_qa && git pull && systemctl restart intranet_qa')
out = stdout.read().decode('utf-8', errors='ignore')
err = stderr.read().decode('utf-8', errors='ignore')
print('OUT:', out)
print('ERR:', err)
