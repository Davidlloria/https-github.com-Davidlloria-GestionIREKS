Option Explicit

Dim shell, files, root, logPath, command, exitCode
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
root = files.GetParentFolderName(WScript.ScriptFullName)
logPath = files.BuildPath(shell.ExpandEnvironmentStrings("%TEMP%"), "GestionIREKS-desktop.log")
shell.CurrentDirectory = root
command = shell.ExpandEnvironmentStrings("%ComSpec%") & " /d /s /c " & _
    Chr(34) & Chr(34) & files.BuildPath(root, "run-desktop.bat") & Chr(34) & _
    " --hidden > " & Chr(34) & logPath & Chr(34) & " 2>&1" & Chr(34)
exitCode = shell.Run(command, 0, True)
If exitCode <> 0 Then
    MsgBox "No se pudo iniciar Gestion IREKS (codigo " & exitCode & ")." & vbCrLf & _
        "Consulta el registro: " & logPath, vbExclamation, "Gestion IREKS"
End If
WScript.Quit exitCode
