$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$all=@()
foreach($folder in @($root,(Join-Path $root 'Core'),$PSScriptRoot)) { $all+=@(Get-ChildItem -LiteralPath $folder -File | Where-Object { $_.Extension -in '.ps1','.psm1' } | ForEach-Object { $_.FullName }) }
$failed=$false
foreach($path in $all) { $tokens=$null;$errors=$null;[void][System.Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errors);foreach($error in $errors){Write-Host $path $error.Extent.StartLineNumber $error.Message;$failed=$true} }
if($failed){exit 1};Write-Host 'PowerShell source syntax checks passed.'
