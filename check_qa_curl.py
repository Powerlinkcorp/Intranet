import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.0.1.179', username='root', password='Redes2010')

def run(cmd):
    print(f"--- RUNNING: {cmd} ---")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    if out: print("STDOUT:\n" + out.encode('ascii', errors='ignore').decode())
    print("\n")

# Check if port 8001 (QA uvicorn) is responding
run("curl -s -I http://127.0.0.1:8001/login")

# Check if port 8080 (Apache for QA) is responding
run("curl -s -I http://127.0.0.1:8080/login")

