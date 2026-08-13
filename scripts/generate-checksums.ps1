[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ReleaseDirectory
)

$ErrorActionPreference = "Stop"
$releasePath = (Resolve-Path $ReleaseDirectory).Path
$assets = @(
    "sanityops-cli-darwin-arm64",
    "sanityops-cli-darwin-x64",
    "sanityops-cli-linux-x64",
    "sanityops-cli-linux-arm64",
    "sanityops-cli-win-x64.exe",
    "sanityops-cli-win-arm64.exe"
)

$lines = foreach ($asset in $assets) {
    $path = Join-Path $releasePath $asset
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        "{0}  {1}" -f (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant(), $asset
    }
}

if (-not $lines) { throw "No sanityops CLI release binaries found in $releasePath" }
$lines | Set-Content -NoNewline -Encoding utf8 (Join-Path $releasePath "checksums.txt")
Add-Content -Encoding utf8 (Join-Path $releasePath "checksums.txt") ""
Write-Host "Generated checksums.txt for $($lines.Count) asset(s)."
