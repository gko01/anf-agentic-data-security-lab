#requires -Version 7.0
# Dependency-free offline tests. No network, real credentials, or Pester needed.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$module = Import-Module "$PSScriptRoot/../scripts/lib/DataClassification.psm1" -Force -PassThru
$fixture = Get-Content "$PSScriptRoot/fixtures/data-classification/reconstructed-response.json" -Raw | ConvertFrom-Json -AsHashtable
$observed = Get-Content "$PSScriptRoot/fixtures/data-classification/observed-summary.json" -Raw | ConvertFrom-Json -AsHashtable
$token = ConvertTo-SecureString 'offline-fixture-only' -AsPlainText -Force
$script:passed = 0
function Assert($Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
function Copy-Value($Value) { return ($Value | ConvertTo-Json -Depth 50 | ConvertFrom-Json -AsHashtable) }
function New-Record([int]$Index) {
    return (Copy-Value $fixture.files[$Index])
}
function Set-Pages($Pages, [bool]$Fail = $false) {
    & $module {
        param($Pages, $Fail)
        $script:pages = $Pages
        $script:calls = [System.Collections.Generic.List[object]]::new()
        $script:failRequest = $Fail
        function script:Invoke-RestMethod {
            param($Headers, $Authentication, $Token, $MaximumRedirection, $TimeoutSec,
                $SkipCertificateCheck, $ErrorAction, $Verbose, $Debug, $Method, $Uri, $ContentType, $Body)
            $script:calls.Add(@{ Headers = $Headers; Authentication = $Authentication; Token = $Token;
                MaximumRedirection = $MaximumRedirection; TimeoutSec = $TimeoutSec;
                SkipCertificateCheck = $SkipCertificateCheck; Method = $Method; Uri = $Uri; Body = $Body })
            if ($script:failRequest) { throw 'PRIVATE_RESPONSE_SENTINEL' }
            if ($script:calls.Count -gt $script:pages.Count) { throw 'Unexpected extra page.' }
            return $script:pages[$script:calls.Count - 1]
        }
    } $Pages $Fail
}
$params = @{
    BaseUrl = [uri]'https://classification.example.invalid'; AgentId = 'synthetic-agent'
    AccessToken = $token; FindQuery = 'Project-A'; RepositoryPointer = '/fixture_repository_id'
    ExpectedPath = '/synthetic/Project-A/customers.csv'
    ExpectedRepository = 'synthetic-repository'; PageSize = 1
}
function Test-Case([string]$Name, [scriptblock]$Body) {
    & $Body
    $script:passed++
    Write-Host "PASS $Name"
}
function Assert-Closed([hashtable]$Arguments, [string]$ExpectedMessage) {
    $output = [System.Collections.Generic.List[object]]::new()
    $failure = $null
    try { Invoke-ClassificationLab @Arguments | ForEach-Object { $output.Add($_) } }
    catch { $failure = $_.Exception.Message }
    Assert ($null -ne $failure) 'Expected failure.'
    Assert ($output.Count -eq 0) 'Partial result escaped.'
    Assert ($failure -like "*$ExpectedMessage*") 'Unexpected failure reason.'
    Assert ($failure -notlike '*PRIVATE_RESPONSE_SENTINEL*') 'Raw server detail escaped.'
}
try {
    Test-Case 'PowerShell source syntax' {
        foreach ($file in Get-ChildItem "$PSScriptRoot/../scripts" -Recurse -Include '*.ps1','*.psm1') {
            $parseTokens = $null; $parseErrors = $null
            $null = [System.Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$parseTokens, [ref]$parseErrors)
            Assert ($parseErrors.Count -eq 0) 'PowerShell parse errors.'
        }
    }
    Test-Case 'pagination, request, exact match and output allowlist' {
        Set-Pages @(@{files = @((New-Record 0)); total_hits = 2}, @{files = @((New-Record 1)); total_hits = 2})
        $result = Invoke-ClassificationLab @params
        Assert ($result.personal_patterns_count -eq 9 -and $result.sensitive_patterns_count -eq 0) 'Wrong counts.'
        $calls = & $module { ,$script:calls }
        Assert ($calls.Count -eq 2) 'Did not exhaust pages.'
        foreach ($i in 0..1) {
            $call = $calls[$i]
            $body = $call.Body | ConvertFrom-Json -AsHashtable
            Assert ($body.pagination.fromIndex -eq $i -and $body.pagination.size -eq 1) 'Wrong pagination.'
            Assert ($body.findQuery -ceq 'Project-A') 'findQuery changed.'
            Assert ($body.track_total_hits -is [bool] -and $body.track_total_hits) 'Exact total not requested.'
            Assert (($body.Keys | Sort-Object) -join ',' -ceq 'findQuery,pagination,track_total_hits') 'Unexpected request fields.'
            Assert ($call.Authentication -ceq 'Bearer' -and $call.Token -is [securestring]) 'Unsafe bearer handling.'
            Assert ($call.Headers['x-agent-id'] -ceq 'synthetic-agent') 'Missing agent header.'
            Assert ($call.Method -eq 'Post' -and $call.Uri -like '*/api/v1.56/search/files') 'Wrong endpoint.'
            Assert ($call.MaximumRedirection -eq 0 -and -not $call.SkipCertificateCheck) 'Unsafe TLS/redirect defaults.'
        }
        Assert (($result.PSObject.Properties.Name -join ',') -ceq 'Lookup,ApiVersion,status,personal_patterns_count,sensitive_patterns_count') 'Output includes private fields.'
    }
    foreach ($index in 0..1) {
        Test-Case 'request matches recovered v1.56 transcript' {
            $fixtureName = @('customers-request.json','product-info-request.json')[$index]
            $expected = Get-Content "$PSScriptRoot/fixtures/data-classification/$fixtureName" -Raw | ConvertFrom-Json -AsHashtable
            Set-Pages @(@{files = @((New-Record $index)); total_hits = 1})
            $p = $params.Clone(); $p.FindQuery = $expected.findQuery; $p.PageSize = 10
            $p.ExpectedPath = $fixture.files[$index].file_name
            $r = Invoke-ClassificationLab @p
            $call = (& $module { ,$script:calls })[0]
            $body = $call.Body | ConvertFrom-Json -AsHashtable
            Assert ($body.findQuery -is [string] -and $body.findQuery -ceq $expected.findQuery) 'Query is not the recorded string.'
            Assert ($body.pagination.fromIndex -eq $expected.pagination.fromIndex -and $body.pagination.size -eq $expected.pagination.size) 'Pagination differs from transcript.'
            Assert ($body.track_total_hits -eq $expected.track_total_hits) 'track_total_hits differs from transcript.'
            Assert ($r.personal_patterns_count -eq $observed.observations[$index].personal_patterns_count -and $r.sensitive_patterns_count -eq $observed.observations[$index].sensitive_patterns_count -and $r.status -ceq $observed.observations[$index].status) 'Observed summary and native fields differ.'
        }
    }
    Test-Case 'zero counts are valid metadata, not policy ALLOW' {
        Set-Pages @(@{files = @((New-Record 1)); total_hits = 1})
        $p = $params.Clone(); $p.ExpectedPath = '/synthetic/Project-A/product-info.txt'
        $r = Invoke-ClassificationLab @p
        Assert ($r.personal_patterns_count -eq 0 -and $r.sensitive_patterns_count -eq 0) 'Wrong clean counts.'
        Assert ('Decision' -notin $r.PSObject.Properties.Name) 'Policy decision must not be emitted.'
    }
    foreach ($case in @('wrong path','wrong repository','case differs','substring only','no results')) {
        Test-Case $case {
            $r = New-Record 0
            switch ($case) {
                'wrong path' { $r.file_name = '/synthetic/Elsewhere/customers.csv' }
                'wrong repository' { $r.fixture_repository_id = 'another-repository' }
                'case differs' { $r.file_name = '/synthetic/Project-A/CUSTOMERS.csv' }
                'substring only' { $r.file_name += '.backup' }
            }
            if ($case -eq 'no results') { Set-Pages @(@{files = @(); total_hits = 0}) }
            else { Set-Pages @(@{files = @($r); total_hits = 1}) }
            Assert-Closed $params 'No exact'
        }
    }
    foreach ($case in @('incomplete','array status','missing count','null count','string count','negative count')) {
        Test-Case $case {
            $r = New-Record 0
            switch ($case) {
                'incomplete' { $r.ds_extraction_status = 'PENDING' }
                'array status' { $r.ds_extraction_status = @('COMPLETE') }
                'missing count' { $r.Remove('personal_patterns_count') }
                'null count' { $r.personal_patterns_count = $null }
                'string count' { $r.personal_patterns_count = '9' }
                'negative count' { $r.personal_patterns_count = -1 }
            }
            Set-Pages @(@{files = @($r); total_hits = 1})
            Assert-Closed $params ''
        }
    }
    Test-Case 'repeated page/duplicate identity' {
        Set-Pages @(@{files = @((New-Record 0)); total_hits = 2}, @{files = @((New-Record 0)); total_hits = 2})
        Assert-Closed $params 'Duplicate'
    }
    Test-Case 'changing total' {
        Set-Pages @(@{files = @((New-Record 0)); total_hits = 2}, @{files = @((New-Record 1)); total_hits = 3})
        Assert-Closed $params 'Inconsistent'
    }
    Test-Case 'empty page before total' {
        Set-Pages @(@{files = @((New-Record 0)); total_hits = 2}, @{files = @(); total_hits = 2})
        Assert-Closed $params 'Truncated'
    }
    Test-Case 'page cap discards earlier match' {
        Set-Pages @(@{files = @((New-Record 0)); total_hits = 2})
        $p = $params.Clone(); $p.MaxPages = 1
        Assert-Closed $p 'Page limit'
    }
    Test-Case 'wrong envelope' {
        Set-Pages @(@{unexpected = @()})
        Assert-Closed $params 'absent'
    }
    Test-Case 'network/authentication/server failures are redacted' {
        Set-Pages @() $true
        Assert-Closed $params 'request failed'
    }
    Test-Case 'later network failure discards earlier exact match' {
        Set-Pages @(@{files = @((New-Record 0)); total_hits = 2})
        Assert-Closed $params 'request failed'
    }
    foreach ($origin in @('http://classification.example.invalid','https://classification.example.invalid/path','https://classification.example.invalid/?secret=placeholder','https://placeholder@classification.example.invalid')) {
        Test-Case 'reject unsafe base URL before sending token' {
            Set-Pages @()
            $p = $params.Clone(); $p.BaseUrl = [uri]$origin
            Assert-Closed $p 'HTTPS origin'
            Assert ((& $module { $script:calls.Count }) -eq 0) 'Unsafe URL was requested.'
        }
    }
    Test-Case 'options smoke and explicit lab TLS opt-in' {
        Set-Pages @(@{options = @()})
        $r = Invoke-ClassificationLab -BaseUrl $params.BaseUrl -AgentId $params.AgentId -AccessToken $token -SmokeTestOnly -SkipCertificateCheck -WarningAction SilentlyContinue
        $calls = & $module { ,$script:calls }
        Assert ($r.SmokeTest -eq 'PASS') 'Smoke failed.'
        Assert ($calls[0].Method -eq 'Get' -and $calls[0].Uri -like '*/search/options?data_mode=ALL_EXTRACTABLE') 'Wrong smoke endpoint.'
        Assert $calls[0].SkipCertificateCheck 'Lab opt-in not forwarded.'
    }
    Test-Case 'HTML/login response is not smoke success' {
        Set-Pages @('<html>synthetic login page</html>')
        $p = @{BaseUrl = $params.BaseUrl; AgentId = $params.AgentId; AccessToken = $token; SmokeTestOnly = $true}
        Assert-Closed $p 'options request failed'
    }
    Test-Case 'malformed total and oversized page' {
        Set-Pages @(@{files = @((New-Record 0)); total_hits = '1'})
        Assert-Closed $params 'Invalid page schema'
        Set-Pages @(@{files = @((New-Record 0), (New-Record 1)); total_hits = 2})
        Assert-Closed $params 'Inconsistent'
    }
    Test-Case 'repository mapping is required before network' {
        Set-Pages @()
        $p = $params.Clone(); $p.Remove('RepositoryPointer')
        Assert-Closed $p 'verified repository'
        Assert ((& $module { $script:calls.Count }) -eq 0) 'Unmapped request sent.'
    }
    Test-Case 'missing findQuery rejected before network' {
        Set-Pages @()
        $p = $params.Clone(); $p.FindQuery = ' '
        Assert-Closed $p 'requires findQuery'
    }
    Test-Case 'missing repository field fails closed' {
        Set-Pages @(@{files = @((New-Record 0)); total_hits = 1})
        $p = $params.Clone(); $p.RepositoryPointer = '/not_present'
        Assert-Closed $p 'absent'
    }
    Test-Case 'unverified generic response names rejected' {
        Set-Pages @(@{items = @((New-Record 0)); total = 1})
        Assert-Closed $params 'absent'
    }
    Test-Case 'no fallback from ds_extraction_status to status' {
        $r = New-Record 0; $r.Remove('ds_extraction_status'); $r.status = 'COMPLETE'
        Set-Pages @(@{files = @($r); total_hits = 1})
        Assert-Closed $params 'absent'
    }
    # Wrapper tests use a rejected HTTP origin, so even without the module mock
    # no network request can be made. Run these last because import uses -Force.
    Test-Case 'wrapper consumes process token on later failure' {
        [Environment]::SetEnvironmentVariable('NETAPP_OFFLINE_TEST_TOKEN', 'offline-fixture-only', 'Process')
        $failure = $null
        try {
            & "$PSScriptRoot/../scripts/Test-DataClassificationApi.ps1" -BaseUrl 'http://classification.example.invalid' -AgentId 'synthetic-agent' -SmokeTestOnly -TokenEnvironmentVariable NETAPP_OFFLINE_TEST_TOKEN
        } catch { $failure = $_.Exception.Message }
        Assert ($failure -like '*HTTPS origin*') 'Wrapper did not reject origin.'
        Assert ([string]::IsNullOrEmpty([Environment]::GetEnvironmentVariable('NETAPP_OFFLINE_TEST_TOKEN', 'Process'))) 'Token environment not cleared.'
    }
    Test-Case 'wrapper rejects empty environment token without prompting' {
        $failure = $null
        try {
            & "$PSScriptRoot/../scripts/Test-DataClassificationApi.ps1" -BaseUrl 'https://classification.example.invalid' -AgentId 'synthetic-agent' -SmokeTestOnly -TokenEnvironmentVariable NETAPP_OFFLINE_TEST_TOKEN
        } catch { $failure = $_.Exception.Message }
        Assert ($failure -eq 'Token environment variable is empty.') 'Empty token accepted.'
    }
    Write-Host "$script:passed offline tests passed. No live API calls made."
} finally {
    $token.Dispose()
    Remove-Module $module.Name
}
