[CmdletBinding()]
param(
    [string]$Version = "latest",
    [string]$InstallDir = $(if ($env:sanityops_CLI_INSTALL_DIR) { $env:sanityops_CLI_INSTALL_DIR } else { Join-Path $HOME ".sanityops\bin" }),
    [string]$BaseUrl = $(if ($env:sanityops_CLI_BASE_URL) { $env:sanityops_CLI_BASE_URL } else { "https://downloads.sanityops.org/sanityops-cli" }),
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Fail([string]$Message) { throw "sanityops CLI installation failed: $Message" }
function Get-RemoteFile([string]$Url, [string]$Destination) {
    try {
        Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing
    } catch {
        Fail "Unable to download $Url. $($_.Exception.Message)"
    }
}

if ([string]::IsNullOrWhiteSpace($BaseUrl)) { Fail "BaseUrl cannot be empty" }
$BaseUrl = $BaseUrl.TrimEnd('/')

$rawArchitecture = $env:PROCESSOR_ARCHITEW6432
if ([string]::IsNullOrWhiteSpace($rawArchitecture)) {
    $rawArchitecture = $env:PROCESSOR_ARCHITECTURE
}
if ([string]::IsNullOrWhiteSpace($rawArchitecture)) {
    Fail "Unable to determine the Windows CPU architecture"
}

switch ($rawArchitecture.ToLowerInvariant()) {
    "amd64" { $asset = "sanityops-cli-win-x64.exe" }
    "x64" { $asset = "sanityops-cli-win-x64.exe" }
    "arm64" { $asset = "sanityops-cli-win-arm64.exe" }
    default { Fail "Unsupported Windows architecture: $rawArchitecture" }
}

$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("sanityops-cli-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $tempDir | Out-Null
try {
    if ($Version -eq "latest") {
        $manifestPath = Join-Path $tempDir "release.json"
        Get-RemoteFile "$BaseUrl/latest/release.json" $manifestPath
        $manifest = Get-Content -Raw -Path $manifestPath | ConvertFrom-Json
        $Version = [string]$manifest.version
        if ([string]::IsNullOrWhiteSpace($Version)) { Fail "Release manifest does not contain version" }
    }

    $releaseUrl = "$BaseUrl/$Version"
    $binaryPath = Join-Path $tempDir $asset
    $checksumsPath = Join-Path $tempDir "checksums.txt"
    Write-Host "Installing sanityops CLI $Version for Windows/$architecture"
    Get-RemoteFile "$releaseUrl/$asset" $binaryPath
    Get-RemoteFile "$releaseUrl/checksums.txt" $checksumsPath

    $checksumLine = Get-Content -Path $checksumsPath | Where-Object {
        if ([string]::IsNullOrWhiteSpace($_)) { return $false }
        $parts = $_.Trim() -split '\s+', 2
        $parts.Count -eq 2 -and -not [string]::IsNullOrWhiteSpace($parts[1]) -and $parts[1].TrimStart('*') -eq $asset
    } | Select-Object -First 1
    if (-not $checksumLine) { Fail "No checksum for $asset in checksums.txt" }
    $expectedHashToken = ($checksumLine.Trim() -split '\s+')[0]
    if ([string]::IsNullOrWhiteSpace($expectedHashToken)) { Fail "Invalid checksum entry for $asset" }
    $expectedHash = $expectedHashToken.ToLowerInvariant()
    $fileHash = Get-FileHash -Path $binaryPath -Algorithm SHA256
    if ([string]::IsNullOrWhiteSpace($fileHash.Hash)) { Fail "Unable to calculate SHA-256 for $asset" }
    $actualHash = $fileHash.Hash.ToLowerInvariant()
    if ($actualHash -ne $expectedHash) { Fail "Checksum verification failed for $asset" }

    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    $target = Join-Path $InstallDir "sanityops-cli.exe"
    if ((Test-Path $target) -and -not $Force) {
        $answer = Read-Host "$target already exists. Replace it? [y/N]"
        if ($answer -notmatch '^(?i:y|yes)$') { Write-Host "Installation cancelled."; return }
    }

    # Move only after checksum verification; replacing a running binary is retried once.
    Copy-Item -Force -Path $binaryPath -Destination $target
    & $target --version | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail "Installed binary failed verification" }

    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $pathEntries = if ([string]::IsNullOrWhiteSpace($userPath)) {
        @()
    } else {
        @($userPath -split ';' | Where-Object { $_ })
    }
    if ($pathEntries -notcontains $InstallDir) {
        [Environment]::SetEnvironmentVariable("Path", (($pathEntries + $InstallDir) -join ';'), "User")
    }
    if (($env:Path -split ';') -notcontains $InstallDir) { $env:Path = "$InstallDir;$env:Path" }

    Write-Host "Installed sanityops CLI $Version to $target" -ForegroundColor Green
    Write-Host "Run: sanityops-cli --help"
} finally {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $tempDir
}
