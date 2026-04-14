import psutil

for p in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
    if p.info['cmdline'] and 'buildmind' in ' '.join(p.info['cmdline']):
        print(f"PID: {p.info['pid']}, CWD: {p.info['cwd']}, CMD: {' '.join(p.info['cmdline'])}")
