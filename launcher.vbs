Option Explicit

Dim shell, fso, base, dataDir, venvPythonw, appPythonw, appPython, fallbackPythonw
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

base = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = base

dataDir = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\VozaraApp"
venvPythonw = dataDir & "\.venv\Scripts\pythonw.exe"
appPythonw = base & "\runtime\python\pythonw.exe"
appPython = base & "\runtime\python\python.exe"
fallbackPythonw = "pythonw.exe"

shell.Environment("PROCESS")("TCL_LIBRARY") = base & "\runtime\python\tcl\tcl8.6"
shell.Environment("PROCESS")("TK_LIBRARY") = base & "\runtime\python\tcl\tk8.6"

If fso.FileExists(venvPythonw) Then
    shell.Run """" & venvPythonw & """ """ & base & "\app.py""", 0, False
ElseIf fso.FileExists(appPythonw) Then
    shell.Run """" & appPythonw & """ """ & base & "\main.py""", 0, False
Else
    shell.Run fallbackPythonw & " """ & base & "\main.py""", 0, False
End If
