import os
import signal
import subprocess
import time

cmd = 'motion'
# The os.setsid() is passed in the argument preexec_fn so
# it's run after the fork() and before  exec() to run the shell.
pro = subprocess.Popen(cmd, stdout=subprocess.PIPE, 
                       shell=True, preexec_fn=os.setsid) 

time.sleep(100)

os.killpg(os.getpgid(pro.pid), signal.SIGTERM)  # Send the signal to all the process groups
