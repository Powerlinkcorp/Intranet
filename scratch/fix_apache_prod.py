import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('10.0.1.179', username='root', password='Redes2010')

sftp = client.open_sftp()
try:
    with sftp.file('/etc/apache2/sites-available/intranet.conf', 'r') as f:
        conf = f.read().decode()
    if 'ProxyPass /api/ws/chat ws://' not in conf:
        # insert it before ProxyPass / http...
        conf = conf.replace('ProxyPass / http://127.0.0.1:8000/', 'ProxyPass /api/ws/chat ws://127.0.0.1:8000/api/ws/chat\n    ProxyPassReverse /api/ws/chat ws://127.0.0.1:8000/api/ws/chat\n    ProxyPass / http://127.0.0.1:8000/')
        with sftp.file('/etc/apache2/sites-available/intranet.conf', 'w') as f:
            f.write(conf)
except Exception as e:
    print('Failed:', e)
sftp.close()

stdin, stdout, stderr = client.exec_command('systemctl restart apache2')
