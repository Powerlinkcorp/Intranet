import paramiko

conf = """<VirtualHost *:8080>
    ServerName pow-intranet-qa
    
    ProxyPreserveHost On
    ProxyPass /api/ws/chat ws://127.0.0.1:8001/api/ws/chat
    ProxyPassReverse /api/ws/chat ws://127.0.0.1:8001/api/ws/chat
    
    ProxyPass / http://127.0.0.1:8001/
    ProxyPassReverse / http://127.0.0.1:8001/
    
    ErrorLog ${APACHE_LOG_DIR}/qa-error.log
    CustomLog ${APACHE_LOG_DIR}/qa-access.log combined
</VirtualHost>"""

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('10.0.1.179', username='root', password='Redes2010')

sftp = client.open_sftp()
with sftp.file('/etc/apache2/sites-available/intranet-qa.conf', 'w') as f:
    f.write(conf)
sftp.close()

stdin, stdout, stderr = client.exec_command('a2enmod proxy_wstunnel && systemctl restart apache2')
print('STDOUT:\n', stdout.read().decode())
print('STDERR:\n', stderr.read().decode())
