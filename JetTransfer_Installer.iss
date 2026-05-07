[Setup]
AppName=JetTransfer
AppVersion=2.0
AppPublisher=Antigravity Desktop App
AppPublisherURL=https://asiselektronik.com.tr
DefaultDirName={localappdata}\JetTransfer
DefaultGroupName=JetTransfer
AllowNoIcons=yes
; Output location
OutputDir=.\Output
OutputBaseFilename=JetTransfer_Windows11_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
DisableProgramGroupPage=yes

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; IMPORTANT: Run PyInstaller first! Then compile this script.
Source: ".\dist\JetTransfer\JetTransfer.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: ".\dist\JetTransfer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTA: Ensure you don't overwrite any local user db if they upgrade (use skipifsourcedoesntexist or don't include db in install)

[Icons]
Name: "{group}\JetTransfer"; Filename: "{app}\JetTransfer.exe"
Name: "{autodesktop}\JetTransfer"; Filename: "{app}\JetTransfer.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\JetTransfer.exe"; Description: "{cm:LaunchProgram,JetTransfer}"; Flags: nowait postinstall skipifsilent
