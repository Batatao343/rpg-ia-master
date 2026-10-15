<#
 SPEC-198: generates an UPLOAD keystore + signing.properties OUTSIDE the repo/OneDrive. Refuses to overwrite.
 Play App Signing holds the real app-signing key; this key only proves uploads are yours (resettable via Play support,
 but BACK IT UP offline anyway). Never prints the password.
 Usage: powershell -File scripts/android/new_upload_keystore.ps1 [-Dir $env:USERPROFILE\.rpg-signing] [-Alias upload] [-Dname "CN=Valoria Upload, O=<titular>, C=BR"]
#>
param([string]$Dir = "$env:USERPROFILE\.rpg-signing", [string]$Alias = 'upload', [string]$Dname = 'CN=Valoria Upload, OU=Dev, O=RPG IA, C=BR')
$ErrorActionPreference = 'Stop'
if ($Dir -match 'OneDrive') { throw 'Refusing: keystore dir must be outside OneDrive.' }
$jdk = Get-ChildItem "$env:LOCALAPPDATA\jdk21" -Directory -Filter 'jdk-21*' -ErrorAction SilentlyContinue | Select-Object -First 1
$keytool = if ($jdk) { Join-Path $jdk.FullName 'bin\keytool.exe' } else { 'keytool' }
New-Item -ItemType Directory -Force $Dir | Out-Null
$ks = Join-Path $Dir 'upload.jks'; $props = Join-Path $Dir 'signing.properties'
if ((Test-Path $ks) -or (Test-Path $props)) { throw "Refusing to overwrite existing $ks / $props" }
$bytes = New-Object byte[] 24; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$pw = ([Convert]::ToBase64String($bytes)) -replace '[^A-Za-z0-9]', 'x'
& $keytool -genkeypair -v -keystore $ks -alias $Alias -keyalg RSA -keysize 2048 -validity 10000 -storepass $pw -keypass $pw -dname $Dname | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'keytool failed' }
$storeFwd = $ks.Replace([string][char]92, '/')
Set-Content -Encoding ascii $props "storeFile=$storeFwd`nstorePassword=$pw`nkeyAlias=$Alias`nkeyPassword=$pw`n"
icacls $Dir /inheritance:r /grant:r "$($env:USERNAME):(OI)(CI)F" | Out-Null
Write-Host "Created $ks and $props (permissions restricted to current user). BACK UP BOTH OFFLINE; do not commit."
