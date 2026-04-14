import psutil

for p in psutil.process_iter(['pid', 'name', 'cmdline']):
    if p.info['cmdline'] and 'buildmind' in ' '.join(p.info['cmdline']):
        print(f"Killing PID: {p.info['pid']}")
        try:
            p.kill()
        except Exception as e:
            print(f"Failed: {e}")
