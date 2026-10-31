"""Small adb UI inspection helper for prototype verification; never clears app data."""
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

adb = str(Path(os.environ["LOCALAPPDATA"]) / "Android/Sdk/platform-tools/adb.exe")


def run(*args):
    return subprocess.check_output([adb, *args], text=True, encoding="utf-8")


def tree():
    run("shell", "uiautomator", "dump", "/sdcard/veridex-window.xml")
    return ET.fromstring(run("shell", "cat", "/sdcard/veridex-window.xml"))


if __name__ == "__main__":
    action = sys.argv[1]
    if action == "dump":
        for node in tree().iter("node"):
            text = node.get("text") or node.get("content-desc")
            if text:
                print(text.encode("ascii", "backslashreplace").decode(), node.get("bounds"), "enabled=" + node.get("enabled"))
    elif action == "tap":
        target = sys.argv[2]
        nodes = [n for n in tree().iter("node") if target in (n.get("text"), n.get("content-desc"))]
        if not nodes:
            raise SystemExit("Visible element not found: " + target)
        x1, y1, x2, y2 = map(int, re.findall(r"\d+", nodes[0].get("bounds")))
        print(run("shell", "input", "tap", str((x1+x2)//2), str((y1+y2)//2)))
    elif action == "screenshot":
        target = Path(sys.argv[2])
        target.parent.mkdir(parents=True, exist_ok=True)
        run("shell", "screencap", "-p", "/sdcard/veridex-screen.png")
        print(run("pull", "/sdcard/veridex-screen.png", str(target)))
    elif action == "text":
        print(run("shell", "input", "text", sys.argv[2].replace(" ", "%s")))
    elif action == "swipe":
        print(run("shell", "input", "swipe", *sys.argv[2:]))
