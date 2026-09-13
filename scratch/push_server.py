import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('10.0.1.179', username='root', password='Redes2010')

cmds = [
    "ssh-keyscan -H github.com >> ~/.ssh/known_hosts",
    "cd /var/www/intranet_qa && git remote set-url origin git@github.com:whe2/IntranetPower.git",
    "cd /var/www/intranet_qa && git config user.email 'qa-server@powerlink.com.ve'",
    "cd /var/www/intranet_qa && git config user.name 'Servidor QA'",
    "cd /var/www/intranet_qa && git add static/uploads/",
    "cd /var/www/intranet_qa && git commit -m 'Sincronizar archivos de servidor QA'",
    "cd /var/www/intranet_qa && git push origin qa"
]

for cmd in cmds:
    stdin, stdout, stderr = client.exec_command(cmd)
    exit_status = stdout.channel.recv_exit_status()
    print(f"[{cmd}] EXITED: {exit_status}")
    print("STDOUT:", stdout.read().decode())
    print("STDERR:", stderr.read().decode())
