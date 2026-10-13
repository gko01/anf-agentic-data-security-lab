#requires -Version 7.0
Set-StrictMode -Version Latest

function Get-JsonPointer {
    param($Value, [string]$Pointer)
    if ($Pointer -eq '') { return ,$Value }
    if (-not $Pointer.StartsWith('/')) { throw 'Invalid contract JSON pointer.' }
    foreach ($part in $Pointer.Substring(1).Split('/')) {
        $key = $part.Replace('~1', '/').Replace('~0', '~')
        if ($Value -isnot [System.Collections.IDictionary] -or -not $Value.Contains($key)) {
            throw 'Required response field is absent.'
        }
        $Value = $Value[$key]
    }
    return ,$Value
}

function Set-JsonPointer {
    param([System.Collections.IDictionary]$Object, [string]$Pointer, $Value)
    if (-not $Pointer.StartsWith('/')) { throw 'Invalid contract JSON pointer.' }
    $parts = $Pointer.Substring(1).Split('/')
    for ($i = 0; $i -lt $parts.Count - 1; $i++) {
        $key = $parts[$i].Replace('~1', '/').Replace('~0', '~')
        if (-not $Object.Contains($key) -or $Object[$key] -isnot [System.Collections.IDictionary]) {
            throw 'Pagination pointer is absent from request template.'
        }
        $Object = $Object[$key]
    }
    $key = $parts[-1].Replace('~1', '/').Replace('~0', '~')
    if (-not $Object.Contains($key)) { throw 'Pagination pointer is absent from request template.' }
    $Object[$key] = $Value
}

function Test-NonnegativeInteger {
    param($Value)
    return (($Value -is [int] -or $Value -is [long]) -and $Value -ge 0)
}

function Invoke-ClassificationLab {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][uri]$BaseUrl,
        [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$AgentId,
        [Parameter(Mandatory)][securestring]$AccessToken,
        [switch]$SmokeTestOnly,
        [System.Collections.IDictionary]$Contract,
        [string]$ExpectedPath,
        [string]$ExpectedRepository,
        [ValidateRange(1, 1000)][int]$PageSize = 100,
        [ValidateRange(1, 10000)][int]$MaxPages = 100,
        [ValidateRange(1, 300)][int]$TimeoutSeconds = 30,
        [switch]$SkipCertificateCheck
    )
    $ErrorActionPreference = 'Stop'
    if (-not $BaseUrl.IsAbsoluteUri -or $BaseUrl.Scheme -cne 'https' -or
        $BaseUrl.UserInfo -or $BaseUrl.Query -or $BaseUrl.Fragment -or $BaseUrl.AbsolutePath -ne '/') {
        throw 'BaseUrl must be an HTTPS origin, without credentials, query, or path.'
    }
    if ($AgentId -match '[\r\n]' -or $AccessToken.Length -eq 0) { throw 'Invalid authentication input.' }
    if ($SkipCertificateCheck) { Write-Warning 'LAB ONLY: server certificate validation is disabled for this call.' }
    $request = @{
        Headers = @{ 'x-agent-id' = $AgentId; Accept = 'application/json' }
        Authentication = 'Bearer'; Token = $AccessToken
        MaximumRedirection = 0; TimeoutSec = $TimeoutSeconds
        SkipCertificateCheck = [bool]$SkipCertificateCheck
        ErrorAction = 'Stop'; Verbose = $false; Debug = $false
    }
    $api = $BaseUrl.GetLeftPart([System.UriPartial]::Authority) + '/api/v1.56'
    if ($SmokeTestOnly) {
        try {
            $response = Invoke-RestMethod @request -Method Get -Uri "$api/search/options?data_mode=ALL_EXTRACTABLE"
            $options = $response | ConvertTo-Json -Depth 100 | ConvertFrom-Json -AsHashtable
            if ($options -isnot [System.Collections.IDictionary] -or
                -not $options.Contains('options') -or $options.options -isnot [array]) {
                throw 'Invalid options response.'
            }
        } catch { throw 'Classification options request failed. No raw response is displayed.' }
        return [pscustomobject]@{ SmokeTest = 'PASS'; ApiVersion = 'v1.56' }
    }
    if (-not $Contract -or [string]::IsNullOrWhiteSpace($ExpectedPath) -or
        [string]::IsNullOrWhiteSpace($ExpectedRepository)) { throw 'Search requires a contract and exact path/repository.' }
    # Contract comes from the deployed instance, not a guessed public API schema.
    foreach ($key in @('requestTemplate','offsetPointer','limitPointer','itemsPointer','totalPointer','pathPointer','repositoryPointer','statusPointer')) {
        if (-not $Contract.Contains($key)) { throw 'Incomplete instance contract.' }
    }
    if ($Contract.requestTemplate -isnot [System.Collections.IDictionary] -or
        -not $Contract.requestTemplate.Contains('findQuery') -or $null -eq $Contract.requestTemplate.findQuery) {
        throw 'Request template must contain findQuery.'
    }
    if ($Contract.offsetPointer -eq $Contract.limitPointer -or
        $Contract.offsetPointer -match '^/findQuery(?:/|$)' -or $Contract.limitPointer -match '^/findQuery(?:/|$)') {
        throw 'Pagination must not overwrite findQuery or share a pointer.'
    }
    $offset = 0L
    $total = $null
    $match = $null
    $seen = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    for ($page = 0; $page -lt $MaxPages; $page++) {
        $body = $Contract.requestTemplate | ConvertTo-Json -Depth 50 | ConvertFrom-Json -AsHashtable
        Set-JsonPointer $body $Contract.offsetPointer $offset
        Set-JsonPointer $body $Contract.limitPointer $PageSize
        try {
            $response = Invoke-RestMethod @request -Method Post -Uri "$api/search/files" -ContentType 'application/json' -Body ($body | ConvertTo-Json -Depth 50 -Compress)
            # Normalize PS objects to dictionaries; never output raw API records.
            $data = $response | ConvertTo-Json -Depth 100 | ConvertFrom-Json -AsHashtable
        } catch { throw 'Classification search request failed. No partial result or raw response is displayed.' }
        $items = Get-JsonPointer $data $Contract.itemsPointer
        $pageTotal = Get-JsonPointer $data $Contract.totalPointer
        if ($items -isnot [array] -or -not (Test-NonnegativeInteger $pageTotal)) { throw 'Invalid page schema.' }
        if ($null -eq $total) { $total = $pageTotal }
        if ($pageTotal -ne $total -or $items.Count -gt $PageSize -or $offset + $items.Count -gt $total) {
            throw 'Inconsistent pagination; no result is trusted.'
        }
        if ($items.Count -eq 0 -and $offset -lt $total) { throw 'Truncated pagination; no result is trusted.' }
        foreach ($item in $items) {
            $path = Get-JsonPointer $item $Contract.pathPointer
            $repository = Get-JsonPointer $item $Contract.repositoryPointer
            if ($path -isnot [string] -or [string]::IsNullOrWhiteSpace($path) -or
                $repository -isnot [string] -or [string]::IsNullOrWhiteSpace($repository)) { throw 'Invalid resource identity.' }
            $identity = ConvertTo-Json -InputObject @($repository, $path) -Compress
            if (-not $seen.Add($identity)) { throw 'Duplicate resource or repeated page; no result is trusted.' }
            if ([string]::Equals($path, $ExpectedPath, [StringComparison]::Ordinal) -and
                [string]::Equals($repository, $ExpectedRepository, [StringComparison]::Ordinal)) {
                $status = Get-JsonPointer $item $Contract.statusPointer
                $personal = Get-JsonPointer $item '/personal_patterns_count'
                $sensitive = Get-JsonPointer $item '/sensitive_patterns_count'
                if ($status -isnot [string] -or $status -cne 'COMPLETE' -or -not (Test-NonnegativeInteger $personal) -or
                    -not (Test-NonnegativeInteger $sensitive)) { throw 'Incomplete or invalid classification; no result is trusted.' }
                $match = [pscustomobject]@{
                    Lookup = 'EXACT_MATCH'; ApiVersion = 'v1.56'; status = 'COMPLETE'
                    personal_patterns_count = $personal; sensitive_patterns_count = $sensitive
                }
            }
        }
        $offset += $items.Count
        if ($offset -eq $total) {
            if ($null -eq $match) { throw 'No exact path/repository match; no result is trusted.' }
            return $match
        }
    }
    throw 'Page limit reached; no partial result is trusted.'
}

Export-ModuleMember -Function Invoke-ClassificationLab
