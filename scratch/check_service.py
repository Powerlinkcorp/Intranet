import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('10.0.1.179', username='root', password='Redes2010')

stdin, stdout, stderr = client.exec_command('systemctl cat intranet_qa')
print('STDOUT:\n', stdout.read().decode())
print('STDERR:\n', stderr.read().decode())
