param([string]$Source='C:\Perdition Sector')
$ErrorActionPreference='Stop'
$repositoryRoot=Split-Path -Parent $PSScriptRoot
$private=Join-Path (Split-Path -Parent $repositoryRoot) 'Private'
$tools=Join-Path $private 'PublisherTools'
$gh=Join-Path $tools 'bin\gh.exe'
$env:GH_CONFIG_DIR=Join-Path $private 'GitHubAuth'
try {
    foreach ($command in @('python','git')) {
        if (-not (Get-Command $command -ErrorAction SilentlyContinue)) { throw "Authoring requires $command on this PC." }
    }
    if (-not [IO.File]::Exists($gh)) {
        [void][IO.Directory]::CreateDirectory($tools)
        $archive=Join-Path $tools 'gh_2.105.0_windows_amd64.zip'
        [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
        $client=New-Object Net.WebClient
        try { $client.DownloadFile('https://github.com/cli/cli/releases/download/v2.105.0/gh_2.105.0_windows_amd64.zip',$archive) } finally { $client.Dispose() }
        if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne '8813a72c899900afaa10e3fec8fbc64b908c89dbfe837e95ed2fa500fc140627') { throw 'GitHub CLI archive failed verification.' }
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [IO.Compression.ZipFile]::ExtractToDirectory($archive,$tools)
    }
    & $gh auth status
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Sign into jjc71ps4 once to enable repository and release uploads.'
        & $gh auth login --hostname github.com --git-protocol https --web
        if ($LASTEXITCODE -ne 0) { throw 'GitHub authentication did not complete.' }
    }
    & python (Join-Path $PSScriptRoot 'publish_beta.py') --source $Source --gh $gh --auth-dir $env:GH_CONFIG_DIR
    if ($LASTEXITCODE -ne 0) { throw 'Beta publishing stopped. Read the preceding error; completed uploads are retained.' }
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

