# Legt die Desktop-Verknuepfung "DbD Map Scout" an (mit Symbol, startet als Administrator).
# Aufruf ueber verknuepfung_erstellen.bat.
param([Parameter(Mandatory = $true)][string]$Root)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath $Root).Path.TrimEnd('\')   # "C:\...\." -> "C:\..."

$desktop = [Environment]::GetFolderPath('Desktop')        # auch bei OneDrive-Desktop richtig
$lnk = Join-Path $desktop 'DbD Map Scout.lnk'
$shell = New-Object -ComObject WScript.Shell
$s = $shell.CreateShortcut($lnk)
$s.TargetPath = Join-Path $Root 'start.bat'
$s.WorkingDirectory = $Root
$s.WindowStyle = 7                                        # minimiert: kein aufblitzendes Konsolenfenster
$s.Description = 'DbD Map Scout - Map-Overlay fuer Dead by Daylight'
$ico = Join-Path $Root 'dbdmapscout.ico'
if (Test-Path $ico) { $s.IconLocation = "$ico,0" }
$s.Save()

# "Als Administrator ausfuehren" setzen: Flag RunAsUser (0x2000) der LinkFlags = Byte 0x15, Bit 0x20
$bytes = [System.IO.File]::ReadAllBytes($lnk)
$bytes[0x15] = $bytes[0x15] -bor 0x20
[System.IO.File]::WriteAllBytes($lnk, $bytes)

Write-Host "Verknuepfung erstellt: $lnk"
