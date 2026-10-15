<#
 SPEC-198: builds a SIGNED release AAB (bundleRelease). Does NOT upload anywhere.
 Reads signing from -SigningProps (default %USERPROFILE%\.rpg-signing\signing.properties) -> env vars consumed by app/build.gradle;
 versionCode/versionName come from web/android/version.properties (single source; -Bump increments VERSION_CODE).
 Usage: powershell -File scripts/android/release_build.ps1 -ServerUrl https://<prod-domain> [-Bump] [-OutDir <dir>]
 Gate: checkReleaseCleartext (Gradle) refuses http:// server.url; cap sync is run WITHOUT CAP_BUILD=debug.
#>
param(
  [Parameter(Mandatory)][string]$ServerUrl,
  [string]$SigningProps = "$env:USERPROFILE\.rpg-signing\signing.properties",
  [string]$OutDir = '',
  [switch]$Bump
)
$ErrorActionPreference = 'Stop'
if ($ServerUrl -notmatch '^https://') { throw 'ServerUrl must be https://' }
$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$android = Join-Path $root 'web\android'
$verFile = Join-Path $android 'version.properties'
if ($Bump) {
  $t = Get-Content $verFile -Raw
  $n = [int]([regex]::Match($t, 'VERSION_CODE=(\d+)').Groups[1].Value) + 1
  Set-Content -Encoding ascii $verFile ($t -replace 'VERSION_CODE=\d+', "VERSION_CODE=$n")
}
if (-not (Test-Path $SigningProps)) { throw "Signing properties not found: $SigningProps (run new_upload_keystore.ps1)" }
$p = @{}; Get-Content $SigningProps | ForEach-Object { if ($_ -match '^\s*([^#=]+)=(.*)$') { $p[$Matches[1].Trim()] = $Matches[2].Trim() } }
$env:RPG_UPLOAD_STORE_FILE = $p.storeFile; $env:RPG_UPLOAD_STORE_PASSWORD = $p.storePassword
$env:RPG_UPLOAD_KEY_ALIAS = $p.keyAlias; $env:RPG_UPLOAD_KEY_PASSWORD = $p.keyPassword
$jdk = Get-ChildItem "$env:LOCALAPPDATA\jdk21" -Directory -Filter 'jdk-21*' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($jdk) { $env:JAVA_HOME = $jdk.FullName; $env:Path = "$($jdk.FullName)\bin;$env:Path" }
Push-Location (Join-Path $root 'web')
try {
  $env:CAP_SERVER_URL = $ServerUrl; Remove-Item Env:CAP_BUILD -ErrorAction SilentlyContinue
  if (-not (Test-Path dist\index.html)) { npm run build; if ($LASTEXITCODE) { throw 'web build failed' } }
  npx cap sync android; if ($LASTEXITCODE) { throw 'cap sync failed' }
  Push-Location android
  try { .\gradlew.bat --no-daemon clean bundleRelease; if ($LASTEXITCODE) { throw 'gradle bundleRelease failed' } } finally { Pop-Location }
} finally { Pop-Location; Remove-Item Env:RPG_UPLOAD_STORE_PASSWORD, Env:RPG_UPLOAD_KEY_PASSWORD -ErrorAction SilentlyContinue }
$aab = Join-Path $android 'app\build\outputs\bundle\release\app-release.aab'
if (-not (Test-Path $aab)) { throw 'AAB not produced' }
if ($OutDir) { New-Item -ItemType Directory -Force $OutDir | Out-Null; Copy-Item $aab $OutDir -Force; $aab = Join-Path $OutDir 'app-release.aab' }
$h = (Get-FileHash $aab -Algorithm SHA256).Hash
Write-Host "AAB: $aab`nSHA256: $h`nversion: $((Get-Content $verFile) -join ' ')"
