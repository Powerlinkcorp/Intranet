import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.0.1.179', username='root', password='Redes2010')

cmds = [
    'cd /var/www/intranet_qa && git fetch',
    'cd /var/www/intranet_qa && git reset --hard origin/qa',
    'systemctl restart intranet_qa'
]

for cmd in cmds:
    print("RUNNING:", cmd)
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='ignore')
    err = stderr.read().decode('utf-8', errors='ignore')
    print("OUT:", out)
    print("ERR:", err)

