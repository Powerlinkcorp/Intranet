import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('10.0.1.179', username='root', password='Redes2010')

# Generate ssh key with empty passphrase
client.exec_command('ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519')
import time
time.sleep(2) # wait for generation

stdin, stdout, stderr = client.exec_command('cat ~/.ssh/id_ed25519.pub')
print('PUBLIC KEY:\n', stdout.read().decode())
