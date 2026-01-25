Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\369\Documents\My Apps\RUNR\app_files"
WshShell.Run "pythonw tray_app.py", 0, False
