; N.E.X.U.S - Windows installer (Inno Setup 6). Built by release.ps1:
;   ISCC.exe /DAppVersion=0.20.5 installer\nexus.iss  ->  dist\release\NEXUS-Setup-0.20.5.exe
; Per-user install (no administrator): the program goes to %LOCALAPPDATA%\Programs\NEXUS, the user's data stays in
; %LOCALAPPDATA%\NEXUS. The choices on the extra pages (profile JSON, AI model, look, voice) are written to
; %LOCALAPPDATA%\NEXUS\install_preset.json and applied once by NEXUS on its first start (nexus/setup_preset.py).

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "N.E.X.U.S"
#define AppExe "NEXUS.exe"
#define Src "..\dist\NEXUS"

[Setup]
AppId={{235CFD85-EC0E-48C8-A885-CA6EA5E934ED}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Bryan Maciel de Almeida
AppPublisherURL=https://github.com/Bryan-M-Almeida/nexusAI
AppSupportURL=https://github.com/Bryan-M-Almeida/nexusAI/issues
AppCopyright=(c) 2026 Bryan Maciel de Almeida
VersionInfoVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\NEXUS
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist\release
OutputBaseFilename=NEXUS-Setup-{#AppVersion}
SetupIconFile=..\assets\nexus.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
WizardImageFile=wizard-large.bmp
WizardSmallImageFile=wizard-small.bmp
LicenseFile=..\LICENSE
InfoBeforeFile=..\NOTICE
Compression=lzma2/max
SolidCompression=yes
LZMANumBlockThreads=4
ShowLanguageDialog=yes
UsePreviousLanguage=no
AppMutex=Local\NEXUS-Assistant-single-instance
CloseApplications=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
pt.TaskDesktop=Criar um atalho na Área de Trabalho
en.TaskDesktop=Create a desktop shortcut
es.TaskDesktop=Crear un acceso directo en el escritorio
pt.TaskStartup=Abrir o NEXUS quando o Windows iniciar
en.TaskStartup=Open NEXUS when Windows starts
es.TaskStartup=Abrir NEXUS al iniciar Windows
pt.GroupExtra=Opções:
en.GroupExtra=Options:
es.GroupExtra=Opciones:
pt.ProfileTitle=Seu perfil (opcional)
en.ProfileTitle=Your profile (optional)
es.ProfileTitle=Tu perfil (opcional)
pt.ProfileDesc=Já tem o arquivo JSON do seu perfil?
en.ProfileDesc=Do you already have your profile JSON file?
es.ProfileDesc=¿Ya tienes el archivo JSON de tu perfil?
pt.ProfileText=Com ele, o NEXUS já abre sabendo seu nome, sua profissão e seus interesses. Deixe em branco para pular: dá para importar depois em Configurações → Geral.
en.ProfileText=With it, NEXUS opens already knowing your name, job and interests. Leave it empty to skip: you can import it later in Settings → General.
es.ProfileText=Con él, NEXUS abre sabiendo tu nombre, profesión e intereses. Déjalo vacío para omitirlo: puedes importarlo después en Configuración → General.
pt.ProfileField=Arquivo do perfil (.json):
en.ProfileField=Profile file (.json):
es.ProfileField=Archivo del perfil (.json):
pt.ModelTitle=Modelo de IA
en.ModelTitle=AI model
es.ModelTitle=Modelo de IA
pt.ModelDesc=Qual NEX-1.0 o NEXUS deve usar?
en.ModelDesc=Which NEX-1.0 should NEXUS use?
es.ModelDesc=¿Qué NEX-1.0 debe usar NEXUS?
pt.ModelAuto=Automático: o recomendado para este PC (%1)
en.ModelAuto=Automatic: the one recommended for this PC (%1)
es.ModelAuto=Automático: el recomendado para este PC (%1)
pt.ModelLite=NEX-1.0 Lite: o mais leve (1,4 GB) · para placas de 4 GB ou sem placa de vídeo
en.ModelLite=NEX-1.0 Lite: the lightest (1.4 GB) · for 4 GB cards or no graphics card
es.ModelLite=NEX-1.0 Lite: el más ligero (1,4 GB) · para tarjetas de 4 GB o sin tarjeta gráfica
pt.ModelMini=NEX-1.0 Mini: equilíbrio (2,5 GB) · placas de 6 GB
en.ModelMini=NEX-1.0 Mini: balanced (2.5 GB) · 6 GB cards
es.ModelMini=NEX-1.0 Mini: equilibrio (2,5 GB) · tarjetas de 6 GB
pt.ModelStd=NEX-1.0: o padrão (5,2 GB) · placas de 8 GB
en.ModelStd=NEX-1.0: the default (5.2 GB) · 8 GB cards
es.ModelStd=NEX-1.0: el estándar (5,2 GB) · tarjetas de 8 GB
pt.ModelPro=NEX-1.0 Pro: o mais inteligente (9,3 GB) · placas de 12 GB ou mais
en.ModelPro=NEX-1.0 Pro: the smartest (9.3 GB) · 12 GB cards or more
es.ModelPro=NEX-1.0 Pro: el más inteligente (9,3 GB) · tarjetas de 12 GB o más
pt.ModelHw=Detectado: %1 · %2 GB de memória de vídeo · %3 GB de RAM. O modelo é baixado pelo NEXUS no primeiro uso (aparece em Configurações → Downloads).
en.ModelHw=Detected: %1 · %2 GB video memory · %3 GB RAM. NEXUS downloads the model on first use (shown in Settings → Downloads).
es.ModelHw=Detectado: %1 · %2 GB de memoria de vídeo · %3 GB de RAM. NEXUS descarga el modelo en el primer uso (aparece en Configuración → Descargas).
pt.NoGpu=sem placa de vídeo dedicada
en.NoGpu=no dedicated graphics card
es.NoGpu=sin tarjeta gráfica dedicada
pt.LookTitle=Aparência e voz
en.LookTitle=Look and voice
es.LookTitle=Apariencia y voz
pt.LookDesc=Como o NEXUS deve aparecer e falar? Tudo pode ser mudado depois.
en.LookDesc=How should NEXUS look and sound? Everything can be changed later.
es.LookDesc=¿Cómo debe verse y hablar NEXUS? Todo se puede cambiar después.
pt.LookCenter=No centro da tela:
en.LookCenter=In the centre of the screen:
es.LookCenter=En el centro de la pantalla:
pt.LookRing=Aro (anéis de luz)
en.LookRing=Ring (light rings)
es.LookRing=Anillo (anillos de luz)
pt.LookPet=PET (a esfera do NEXUS, o olho segue o mouse)
en.LookPet=PET (the NEXUS orb, the eye follows the mouse)
es.LookPet=PET (la esfera de NEXUS, el ojo sigue al ratón)
pt.LookTheme=Tema de cores:
en.LookTheme=Colour theme:
es.LookTheme=Tema de colores:
pt.LookVoice=Voz:
en.LookVoice=Voice:
es.LookVoice=Voz:
pt.VoiceMale=Masculina
en.VoiceMale=Male
es.VoiceMale=Masculina
pt.VoiceFemale=Feminina
en.VoiceFemale=Female
es.VoiceFemale=Femenina
pt.OllamaTitle=Motor da IA (Ollama)
en.OllamaTitle=AI engine (Ollama)
es.OllamaTitle=Motor de IA (Ollama)
pt.OllamaDesc=O NEXUS roda a IA no seu computador com o Ollama.
en.OllamaDesc=NEXUS runs the AI on your computer with Ollama.
es.OllamaDesc=NEXUS ejecuta la IA en tu ordenador con Ollama.
pt.OllamaMissing=O Ollama não foi encontrado neste PC. Sem ele, a conversa com a IA não funciona (agenda, tarefas e o resto funcionam).
en.OllamaMissing=Ollama was not found on this PC. Without it the AI conversation doesn't work (schedule, tasks and the rest do).
es.OllamaMissing=No se encontró Ollama en este PC. Sin él, la conversación con la IA no funciona (agenda, tareas y el resto sí).
pt.OllamaFound=O Ollama já está instalado neste PC. Nada a fazer.
en.OllamaFound=Ollama is already installed on this PC. Nothing to do.
es.OllamaFound=Ollama ya está instalado en este PC. Nada que hacer.
pt.OllamaGet=Baixar e instalar o Ollama agora (ollama.com, ~1 GB, gratuito)
en.OllamaGet=Download and install Ollama now (ollama.com, ~1 GB, free)
es.OllamaGet=Descargar e instalar Ollama ahora (ollama.com, ~1 GB, gratis)
pt.OllamaRun=Instalando o Ollama...
en.OllamaRun=Installing Ollama...
es.OllamaRun=Instalando Ollama...
pt.RemoveData=Apagar também os seus dados do NEXUS (memórias, conversas, agenda, configurações e contas)?%n%nEscolha Não para mantê-los e usá-los numa próxima instalação.
en.RemoveData=Also delete your NEXUS data (memories, conversations, schedule, settings and accounts)?%n%nChoose No to keep them for a future install.
es.RemoveData=¿Borrar también tus datos de NEXUS (memorias, conversaciones, agenda, ajustes y cuentas)?%n%nElige No para conservarlos para una próxima instalación.
pt.Launch=Abrir o N.E.X.U.S
en.Launch=Open N.E.X.U.S
es.Launch=Abrir N.E.X.U.S

[Tasks]
Name: "desktopicon"; Description: "{cm:TaskDesktop}"; GroupDescription: "{cm:GroupExtra}"
Name: "startup"; Description: "{cm:TaskStartup}"; GroupDescription: "{cm:GroupExtra}"; Flags: unchecked

[Files]
Source: "{#Src}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\{#AppExe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "NEXUS"; ValueData: """{app}\{#AppExe}"""; Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:Launch}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Code]
var
  ProfilePage: TInputFileWizardPage;
  ModelPage: TInputOptionWizardPage;
  LookPage: TWizardPage;
  OllamaPage: TWizardPage;
  RingRadio, PetRadio, MaleRadio, FemaleRadio: TNewRadioButton;
  ThemeCombo: TNewComboBox;
  OllamaCheck: TNewCheckBox;
  DownloadPage: TDownloadWizardPage;
  GpuName: String;
  VramGb, RamGb: Extended;
  AutoModel: String;

const
  ThemeIds = 'nexus,amd,emerald,violet,amber,graphite,ice';

function LangCode(): String;
begin
  Result := ActiveLanguage();  { pt / en / es: the names of the [Languages] entries }
end;

{ ---- hardware: the same rule as nexus/models.py recommended() ---------------------------------------------- }
procedure DetectHardware();
var
  Tmp, Cmd: String;
  Lines: TArrayOfString;
  Code: Integer;
  Parts: TStringList;
begin
  GpuName := ''; VramGb := 0; RamGb := 0;
  Tmp := ExpandConstant('{tmp}\nexus-hw.txt');
  Cmd := '-NoProfile -ExecutionPolicy Bypass -Command "' +
    '$k = Get-ItemProperty ''HKLM:\SYSTEM\ControlSet001\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0*'' -ErrorAction SilentlyContinue | ' +
    'Where-Object { $_.''HardwareInformation.qwMemorySize'' } | Sort-Object { [double]$_.''HardwareInformation.qwMemorySize'' } -Descending | Select-Object -First 1; ' +
    '$v = if ($k) { [math]::Round([double]$k.''HardwareInformation.qwMemorySize'' / 1GB * 10) } else { 0 }; ' +
    '$n = if ($k) { $k.DriverDesc } else { '''' }; ' +
    '$r = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB * 10); ' +
    '[IO.File]::WriteAllText(''' + Tmp + ''', ($n + ''|'' + $v + ''|'' + $r))"';
  if Exec('powershell.exe', Cmd, '', SW_HIDE, ewWaitUntilTerminated, Code) and LoadStringsFromFile(Tmp, Lines) and (GetArrayLength(Lines) > 0) then
  begin
    Parts := TStringList.Create;
    try
      Parts.Delimiter := '|';
      Parts.StrictDelimiter := True;
      Parts.DelimitedText := Lines[0];
      if Parts.Count >= 3 then
      begin
        GpuName := Trim(Parts[0]);
        VramGb := StrToIntDef(Parts[1], 0) / 10.0;
        RamGb := StrToIntDef(Parts[2], 0) / 10.0;
      end;
    finally
      Parts.Free;
    end;
  end;
end;

function ModelFor(Vram, Ram: Extended): String;
var
  Ids: array[0..4] of String;
  Need: array[0..4] of Extended;
  Usable, OnGpu, Spill: Extended;
  I: Integer;
begin
  Ids[0] := 'qwen3:1.7b';                     Need[0] := 2.5;
  Ids[1] := 'qwen3:4b-instruct-2507-q4_K_M';  Need[1] := 5.6;
  Ids[2] := 'qwen3:8b';                       Need[2] := 6.6;
  Ids[3] := 'qwen3:14b';                      Need[3] := 10.7;
  Ids[4] := 'qwen3:30b-a3b';                  Need[4] := 19.8;
  Result := '';
  if Vram >= 2 then Usable := Vram - 1.8 else Usable := 0;
  if Usable < 0 then Usable := 0;
  for I := 0 to 4 do
  begin
    OnGpu := Usable / Need[I];
    if OnGpu > 1 then OnGpu := 1;
    Spill := Need[I] - Usable;
    if Spill < 0 then Spill := 0;
    if (Usable > 0) and (Spill <= Ram - 6) and (OnGpu >= 0.75) then
      Result := Ids[I];
  end;
  if Result = '' then
    if Ram >= 12 then Result := 'qwen3:4b-instruct-2507-q4_K_M' else Result := 'qwen3:1.7b';
end;

function ModelName(Id: String): String;
begin
  if Id = 'qwen3:1.7b' then Result := 'NEX-1.0 Lite'
  else if Id = 'qwen3:4b-instruct-2507-q4_K_M' then Result := 'NEX-1.0 Mini'
  else if Id = 'qwen3:8b' then Result := 'NEX-1.0'
  else if Id = 'qwen3:14b' then Result := 'NEX-1.0 Pro'
  else if Id = 'qwen3:30b-a3b' then Result := 'NEX-1.0 Max'
  else Result := Id;
end;

function FmtGb(V: Extended): String;
begin
  Result := IntToStr(Round(V * 10) div 10) + ',' + IntToStr(Round(V * 10) mod 10);
  if ActiveLanguage() = 'en' then StringChangeEx(Result, ',', '.', True);
end;

{ ---- Ollama ---------------------------------------------------------------------------------------------- }
function OllamaInstalled(): Boolean;
begin
  Result := FileExists(ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe')) or
            FileExists(ExpandConstant('{commonpf64}\Ollama\ollama.exe')) or
            (FileSearch('ollama.exe', GetEnv('PATH')) <> '');
end;

{ ---- pages ------------------------------------------------------------------------------------------------ }
function AddLabel(Page: TWizardPage; Top: Integer; Text: String; Bold: Boolean): TNewStaticText;
begin
  Result := TNewStaticText.Create(Page);
  Result.Parent := Page.Surface;
  Result.Top := Top;
  Result.Width := Page.SurfaceWidth;
  Result.WordWrap := True;
  Result.Caption := Text;
  if Bold then Result.Font.Style := [fsBold];
end;

function AddRadio(Page: TWizardPage; Top: Integer; Text: String; Checked: Boolean): TNewRadioButton;
begin
  Result := TNewRadioButton.Create(Page);
  Result.Parent := Page.Surface;
  Result.Top := Top;
  Result.Left := ScaleX(12);
  Result.Width := Page.SurfaceWidth - ScaleX(12);
  Result.Caption := Text;
  Result.Checked := Checked;
end;

procedure InitializeWizard();
var
  Hw, G: String;
  VoicePanel: TPanel;
  Y: Integer;
begin
  DetectHardware();
  AutoModel := ModelFor(VramGb, RamGb);
  Log(Format('NEXUS hardware: "%s" vram=%d/10 GB ram=%d/10 GB -> %s', [GpuName, Round(VramGb * 10), Round(RamGb * 10), AutoModel]));

  ProfilePage := CreateInputFilePage(wpSelectTasks, CustomMessage('ProfileTitle'), CustomMessage('ProfileDesc'),
    CustomMessage('ProfileText'));
  ProfilePage.Add(CustomMessage('ProfileField'), 'JSON (*.json)|*.json|*.*|*.*', '.json');

  ModelPage := CreateInputOptionPage(ProfilePage.ID, CustomMessage('ModelTitle'), CustomMessage('ModelDesc'), '', True, False);
  if GpuName = '' then G := CustomMessage('NoGpu') else G := GpuName;
  Hw := FmtMessage(CustomMessage('ModelHw'), [G, FmtGb(VramGb), FmtGb(RamGb)]);
  ModelPage.SubCaptionLabel.Caption := Hw;
  ModelPage.Add(FmtMessage(CustomMessage('ModelAuto'), [ModelName(AutoModel)]));
  ModelPage.Add(CustomMessage('ModelLite'));
  ModelPage.Add(CustomMessage('ModelMini'));
  ModelPage.Add(CustomMessage('ModelStd'));
  ModelPage.Add(CustomMessage('ModelPro'));
  ModelPage.SelectedValueIndex := 0;

  LookPage := CreateCustomPage(ModelPage.ID, CustomMessage('LookTitle'), CustomMessage('LookDesc'));
  Y := 0;
  AddLabel(LookPage, Y, CustomMessage('LookCenter'), True);
  RingRadio := AddRadio(LookPage, Y + ScaleY(18), CustomMessage('LookRing'), True);
  PetRadio := AddRadio(LookPage, Y + ScaleY(38), CustomMessage('LookPet'), False);
  Y := Y + ScaleY(68);
  AddLabel(LookPage, Y, CustomMessage('LookTheme'), True);
  ThemeCombo := TNewComboBox.Create(LookPage);
  ThemeCombo.Parent := LookPage.Surface;
  ThemeCombo.Top := Y + ScaleY(18);
  ThemeCombo.Left := ScaleX(12);
  ThemeCombo.Width := ScaleX(220);
  ThemeCombo.Style := csDropDownList;
  ThemeCombo.Items.Add('NEXUS (azul / blue)');
  ThemeCombo.Items.Add('AMD (vermelho / red)');
  ThemeCombo.Items.Add('Emerald (verde / green)');
  ThemeCombo.Items.Add('Violet (roxo / purple)');
  ThemeCombo.Items.Add('Amber (âmbar)');
  ThemeCombo.Items.Add('Graphite (cinza / grey)');
  ThemeCombo.Items.Add('Ice (gelo / ice)');
  ThemeCombo.ItemIndex := 0;
  Y := Y + ScaleY(56);
  AddLabel(LookPage, Y, CustomMessage('LookVoice'), True);
  VoicePanel := TPanel.Create(LookPage);  { radio buttons group by parent: the voice needs its own }
  VoicePanel.Parent := LookPage.Surface;
  VoicePanel.Top := Y + ScaleY(18);
  VoicePanel.Left := 0;
  VoicePanel.Width := LookPage.SurfaceWidth;
  VoicePanel.Height := ScaleY(44);
  VoicePanel.BevelOuter := bvNone;
  MaleRadio := TNewRadioButton.Create(LookPage);
  MaleRadio.Parent := VoicePanel;
  MaleRadio.Top := 0; MaleRadio.Left := ScaleX(12); MaleRadio.Width := ScaleX(200);
  MaleRadio.Caption := CustomMessage('VoiceMale'); MaleRadio.Checked := True;
  FemaleRadio := TNewRadioButton.Create(LookPage);
  FemaleRadio.Parent := MaleRadio.Parent;
  FemaleRadio.Top := ScaleY(20); FemaleRadio.Left := ScaleX(12); FemaleRadio.Width := ScaleX(200);
  FemaleRadio.Caption := CustomMessage('VoiceFemale');

  OllamaPage := CreateCustomPage(LookPage.ID, CustomMessage('OllamaTitle'), CustomMessage('OllamaDesc'));
  OllamaCheck := TNewCheckBox.Create(OllamaPage);
  if OllamaInstalled() then
    AddLabel(OllamaPage, 0, CustomMessage('OllamaFound'), False)
  else
  begin
    AddLabel(OllamaPage, 0, CustomMessage('OllamaMissing'), False);
    OllamaCheck.Parent := OllamaPage.Surface;
    OllamaCheck.Top := ScaleY(48);
    OllamaCheck.Width := OllamaPage.SurfaceWidth;
    OllamaCheck.Caption := CustomMessage('OllamaGet');
    OllamaCheck.Checked := True;
  end;

  DownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing), SetupMessage(msgPreparingDesc), nil);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpReady) and (OllamaCheck.Parent <> nil) and OllamaCheck.Checked then
  begin
    DownloadPage.Clear;
    DownloadPage.Add('https://ollama.com/download/OllamaSetup.exe', 'OllamaSetup.exe', '');
    DownloadPage.Show;
    try
      try
        DownloadPage.Download;
      except
        SuppressibleMsgBox(AddPeriod(GetExceptionMessage), mbError, MB_OK, IDOK);
        OllamaCheck.Checked := False;  { go on without it: NEXUS explains how to install it later }
      end;
    finally
      DownloadPage.Hide;
    end;
  end;
end;

function JsonStr(S: String): String;
begin
  StringChangeEx(S, '\', '\\', True);
  StringChangeEx(S, '"', '\"', True);
  Result := '"' + S + '"';
end;

procedure WritePreset();
var
  Dir, Model, Theme, Json: String;
  Themes: TStringList;
begin
  Dir := ExpandConstant('{param:PRESETDIR|{localappdata}\NEXUS}');  { /PRESETDIR= only for the release tests }
  ForceDirectories(Dir);
  case ModelPage.SelectedValueIndex of
    1: Model := 'qwen3:1.7b';
    2: Model := 'qwen3:4b-instruct-2507-q4_K_M';
    3: Model := 'qwen3:8b';
    4: Model := 'qwen3:14b';
  else
    Model := 'auto';
  end;
  Themes := TStringList.Create;
  try
    Themes.CommaText := ThemeIds;
    Theme := Themes[ThemeCombo.ItemIndex];
  finally
    Themes.Free;
  end;
  Json := '{' +
    '"language": ' + JsonStr(LangCode()) + ', ' +
    '"llm_model": ' + JsonStr(Model) + ', ' +
    '"theme": ' + JsonStr(Theme) + ', ';
  if PetRadio.Checked then Json := Json + '"center_style": "pet", ' else Json := Json + '"center_style": "ring", ';
  if FemaleRadio.Checked then Json := Json + '"voice_gender": "female", ' else Json := Json + '"voice_gender": "male", ';
  Json := Json + '"installer": ' + JsonStr('{#AppVersion}') + '}';
  SaveStringToFile(Dir + '\install_preset.json', Json, False);
  if (ProfilePage.Values[0] <> '') and FileExists(ProfilePage.Values[0]) then
    CopyFile(ProfilePage.Values[0], Dir + '\install_profile.json', False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Code: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    WritePreset();
    if (OllamaCheck.Parent <> nil) and OllamaCheck.Checked and FileExists(ExpandConstant('{tmp}\OllamaSetup.exe')) then
    begin
      WizardForm.StatusLabel.Caption := CustomMessage('OllamaRun');
      Exec(ExpandConstant('{tmp}\OllamaSetup.exe'), '/SILENT /NORESTART /SUPPRESSMSGBOXES', '', SW_SHOW, ewWaitUntilTerminated, Code);
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent and
     (MsgBox(CustomMessage('RemoveData'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES) then
    DelTree(ExpandConstant('{localappdata}\NEXUS'), True, True, True);
end;
