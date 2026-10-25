Option Explicit

Dim shell, files, root, logPath, command, exitCode, python
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
root = files.GetParentFolderName(WScript.ScriptFullName)
' Each launch needs its own log while the application is running.
logPath = files.BuildPath(shell.ExpandEnvironmentStrings("%TEMP%"), _
    "GestionIREKS-desktop-" & files.GetTempName & ".log")
shell.CurrentDirectory = root
python = files.BuildPath(root, ".venv\Scripts\pythonw.exe")
If Not files.FileExists(python) Then python = "pythonw.exe"
command = Chr(34) & python & Chr(34) & " " & _
    Chr(34) & files.BuildPath(root, "run-desktop.pyw") & Chr(34) & " " & _
    Chr(34) & logPath & Chr(34)
' pythonw has no console; normal display mode lets the application's window appear.
exitCode = shell.Run(command, 1, True)
If exitCode <> 0 Then
    MsgBox "No se pudo iniciar Gestion IREKS (codigo " & exitCode & ")." & vbCrLf & _
        "Consulta el registro: " & logPath, vbExclamation, "Gestion IREKS"
End If
WScript.Quit exitCode
