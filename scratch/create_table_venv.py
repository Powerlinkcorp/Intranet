import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('10.0.1.179', username='root', password='Redes2010')

stdin, stdout, stderr = client.exec_command('cd /var/www/intranet_qa && /var/www/intranet_qa/venv/bin/python -c "from database import engine; from models import Base; Base.metadata.create_all(bind=engine)"')
print('STDOUT:\n', stdout.read().decode())
print('STDERR:\n', stderr.read().decode())
