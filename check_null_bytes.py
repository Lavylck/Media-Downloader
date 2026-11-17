import os

def find_null_bytes(root_dir):
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'rb') as f:
                        content = f.read()
                        if b'\x00' in content:
                            print(f"Null byte found in: {path}")
                except Exception as e:
                    print(f"Error reading {path}: {e}")

if __name__ == '__main__':
    find_null_bytes('.')
