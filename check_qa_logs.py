import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.0.1.179', username='root', password='Redes2010')

def run(cmd):
    print(f"--- RUNNING: {cmd} ---")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    if out: print("STDOUT:\n" + out.encode('ascii', errors='ignore').decode())
    if err: print("STDERR:\n" + err.encode('ascii', errors='ignore').decode())
    print("\n")

# Check systemd status
run("systemctl status intranet_qa --no-pager")

# Check recent errors in journalctl
run("journalctl -u intranet_qa --no-pager -p 3 -n 20")

# Check for any fatal python errors or unhandled exceptions in the last 100 lines
run("journalctl -u intranet_qa --no-pager -n 100 | grep -i -E 'traceback|error|exception|critical' | tail -n 20")

