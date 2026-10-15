import paramiko
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

host = "10.0.1.179"
user = "root"
password = "Redes2010"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(host, username=user, password=password, timeout=10)
    
    commands = [
        "cd /var/www/intranet_qa && git fetch powerlink && git reset --hard powerlink/whilly",
        "systemctl restart intranet_qa",
        "cd /var/www/intranet_prod && git fetch powerlink && git reset --hard powerlink/whilly",
        "systemctl restart intranet_prod"
    ]
    
    for cmd in commands:
        print(f"\n--- Ejecutando: {cmd} ---")
        stdin, stdout, stderr = client.exec_command(cmd)
        print(stdout.read().decode('utf-8', errors='replace'))
        err = stderr.read().decode('utf-8', errors='replace')
        if err:
            print("ERROR:", err)

finally:
    client.close()
