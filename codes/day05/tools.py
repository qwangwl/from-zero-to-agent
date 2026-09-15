import os

def list_files():
    return os.listdir(".")

def read_file(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()