import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.0.1.179', username='root', password='Redes2010')

script = '''
sed -i 's/postgres:1234@localhost:5432\/intranet_db/intranet_user:Redes2010@localhost:5432\/intranet_qa/' /var/www/intranet_qa/.env
cat /var/www/intranet_qa/.env | grep DATABASE_URL
systemctl restart intranet_qa
'''
stdin, stdout, stderr = ssh.exec_command(script)
print("OUT:", stdout.read().decode())
print("ERR:", stderr.read().decode())
