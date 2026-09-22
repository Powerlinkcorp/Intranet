import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('10.0.1.179', username='root', password='Redes2010')
_, stdout, stderr = client.exec_command('sed -n "2325,2340p" /var/www/intranet_qa/main.py')
print('OUT:', stdout.read().decode())
