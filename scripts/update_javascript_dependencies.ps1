[CmdletBinding()]
param(
    [ValidatePattern('^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$')]
    [string]$MermaidVersion,
    [switch]$Check
)

$ErrorActionPreference = 'Stop'
$vendorDirectory = Join-Path $PSScriptRoot 'vendor'
$lockPath = Join-Path $vendorDirectory 'javascript-dependencies.json'

function Resolve-VendorFile {
    param([Parameter(Mandatory)][string]$FileName)

    if ([System.IO.Path]::GetFileName($FileName) -ne $FileName) {
        throw "Nom de fichier de dépendance invalide : $FileName"
    }
    $vendorRoot = [System.IO.Path]::GetFullPath($vendorDirectory).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    $resolved = [System.IO.Path]::GetFullPath((Join-Path $vendorDirectory $FileName))
    if (-not $resolved.StartsWith($vendorRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Le fichier de dépendance sort de scripts/vendor : $resolved"
    }
    return $resolved
}

function Get-DependencyLock {
    if (-not (Test-Path -LiteralPath $lockPath -PathType Leaf)) {
        throw "Fichier de verrouillage absent : $lockPath"
    }
    return Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Test-LockedDependencies {
    $lock = Get-DependencyLock
    $rendererPath = Resolve-VendorFile -FileName $lock.mermaid.file
    $licensePath = Resolve-VendorFile -FileName $lock.mermaid.license_file
    if (-not (Test-Path -LiteralPath $rendererPath -PathType Leaf)) {
        throw "Distribution Mermaid locale absente : $rendererPath"
    }
    if (-not (Test-Path -LiteralPath $licensePath -PathType Leaf)) {
        throw "Licence Mermaid locale absente : $licensePath"
    }
    $actualHash = (Get-FileHash -LiteralPath $rendererPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne [string]$lock.mermaid.sha256) {
        throw "Somme SHA-256 Mermaid invalide. Attendu : $($lock.mermaid.sha256) ; obtenu : $actualHash"
    }
    Write-Host "Dépendances JavaScript locales valides : Mermaid $($lock.mermaid.version) ($actualHash)"
}

if ($Check) {
    if ($MermaidVersion) {
        throw 'Ne pas combiner -Check et -MermaidVersion.'
    }
    Test-LockedDependencies
    exit 0
}

if ([string]::IsNullOrWhiteSpace($MermaidVersion)) {
    throw 'Préciser -MermaidVersion <version>, ou utiliser -Check.'
}

$rendererFile = "mermaid-$MermaidVersion.min.js"
$licenseFile = 'MERMAID-LICENSE.txt'
$rendererUrl = "https://cdn.jsdelivr.net/npm/mermaid@$MermaidVersion/dist/mermaid.min.js"
$licenseUrl = "https://cdn.jsdelivr.net/npm/mermaid@$MermaidVersion/LICENSE"
$rendererTarget = Resolve-VendorFile -FileName $rendererFile
$licenseTarget = Resolve-VendorFile -FileName $licenseFile
$rendererDownload = Resolve-VendorFile -FileName ".mermaid-$PID.download.js"
$licenseDownload = Resolve-VendorFile -FileName ".mermaid-license-$PID.download.txt"

try {
    Write-Host "Téléchargement de Mermaid $MermaidVersion…"
    Invoke-WebRequest -Uri $rendererUrl -OutFile $rendererDownload
    Invoke-WebRequest -Uri $licenseUrl -OutFile $licenseDownload

    if ((Get-Item -LiteralPath $rendererDownload).Length -lt 1000000) {
        throw 'La distribution Mermaid téléchargée est anormalement petite.'
    }
    if ((Get-Item -LiteralPath $licenseDownload).Length -lt 100) {
        throw 'La licence Mermaid téléchargée est anormalement petite.'
    }

    $sha256 = (Get-FileHash -LiteralPath $rendererDownload -Algorithm SHA256).Hash.ToLowerInvariant()
    Move-Item -LiteralPath $rendererDownload -Destination $rendererTarget -Force
    Move-Item -LiteralPath $licenseDownload -Destination $licenseTarget -Force

    $newLock = [ordered]@{
        mermaid = [ordered]@{
            version = $MermaidVersion
            file = $rendererFile
            license_file = $licenseFile
            url = $rendererUrl
            license_url = $licenseUrl
            sha256 = $sha256
        }
    }
    $newLock | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $lockPath -Encoding UTF8
    Test-LockedDependencies
    Write-Host 'Mise à jour terminée. Régénérer le site puis exécuter les tests.'
}
finally {
    foreach ($temporaryFile in @($rendererDownload, $licenseDownload)) {
        if (Test-Path -LiteralPath $temporaryFile -PathType Leaf) {
            Remove-Item -LiteralPath $temporaryFile -Force
        }
    }
}
