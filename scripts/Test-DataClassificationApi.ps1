#requires -Version 7.0
<#
.SYNOPSIS
Read-only NetApp Data Classification v1.56 metadata test.
.DESCRIPTION
Prompts securely for a user access token, or consumes a process environment
variable. Search requires an instance-derived contract; see the deployment guide.
Success is metadata evidence, never an ALLOW decision. No file content is read.
#>
[CmdletBinding(DefaultParameterSetName = 'Search')]
param(
    [Parameter(Mandatory)][uri]$BaseUrl,
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$AgentId,
    [securestring]$AccessToken,
    [ValidatePattern('^[A-Za-z_][A-Za-z0-9_]*$')][string]$TokenEnvironmentVariable,
    [Parameter(Mandatory, ParameterSetName = 'Smoke')][switch]$SmokeTestOnly,
    [Parameter(Mandatory, ParameterSetName = 'Search')][string]$ContractPath,
    [Parameter(Mandatory, ParameterSetName = 'Search')][string]$ExpectedPath,
    [Parameter(Mandatory, ParameterSetName = 'Search')][string]$ExpectedRepository,
    [ValidateRange(1, 1000)][int]$PageSize = 100,
    [ValidateRange(1, 10000)][int]$MaxPages = 100,
    [ValidateRange(1, 300)][int]$TimeoutSeconds = 30,
    [switch]$SkipCertificateCheck
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'lib/DataClassification.psm1') -Force
$ownedToken = $false
try {
    if ($AccessToken -and $TokenEnvironmentVariable) { throw 'Choose one token source.' }
    if ($TokenEnvironmentVariable) {
        $plain = [Environment]::GetEnvironmentVariable($TokenEnvironmentVariable, 'Process')
        [Environment]::SetEnvironmentVariable($TokenEnvironmentVariable, $null, 'Process')
        try {
            if ([string]::IsNullOrWhiteSpace($plain)) { throw 'Token environment variable is empty.' }
            $AccessToken = ConvertTo-SecureString $plain -AsPlainText -Force
            $ownedToken = $true
        } finally { $plain = $null }
    } elseif (-not $AccessToken) {
        $AccessToken = Read-Host 'User access token (not refresh token)' -AsSecureString
        $ownedToken = $true
    }
    $argsForLab = @{
        BaseUrl = $BaseUrl; AgentId = $AgentId; AccessToken = $AccessToken
        PageSize = $PageSize; MaxPages = $MaxPages; TimeoutSeconds = $TimeoutSeconds
        SkipCertificateCheck = $SkipCertificateCheck
    }
    if ($SmokeTestOnly) { $argsForLab.SmokeTestOnly = $true }
    else {
        try { $argsForLab.Contract = Get-Content -LiteralPath $ContractPath -Raw | ConvertFrom-Json -AsHashtable }
        catch { throw 'Unable to read local instance contract.' }
        $argsForLab.ExpectedPath = $ExpectedPath
        $argsForLab.ExpectedRepository = $ExpectedRepository
    }
    Invoke-ClassificationLab @argsForLab
} finally {
    if ($ownedToken -and $AccessToken) { $AccessToken.Dispose() }
    $AccessToken = $null
}
