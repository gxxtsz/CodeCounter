import os
import shutil

def rm_dir(path):
    if os.path.exists(path):
        shutil.rmtree(path)

rm_dir("build")
rm_dir("dist")

os.system(r"pyinstaller -Fw --name CodeCounter --icon=.\icon\build_icon.png code_counter.py")

shutil.copytree("icon", "dist/icon")
shutil.copyfile("config.json", "dist/config.json")

shutil.rmtree("build")
os.remove("CodeCounter.spec")