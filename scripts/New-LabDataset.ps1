<#
.SYNOPSIS
    Generates the synthetic test dataset for the ANF Agentic Data Security Lab.

.DESCRIPTION
    Creates a fixed set of synthetic, non-sensitive test files (plus a manifest.json)
    at the given destination path, for later use with NetApp Data Classification
    scanning. All generated content is fictional and safe for a public repository.

    This script does not touch Azure NetApp Files, NetApp Data Classification, or any
    other service directly. It only writes files to the path you provide, which may be
    a mapped Windows drive or a UNC SMB path that already points at your ANF volume/share.

.PARAMETER Path
    Destination directory for the dataset. Can be a mapped drive (e.g. Z:\Project-A)
    or a UNC path (e.g. \\server\share\Project-A). Created if it does not exist.

.PARAMETER Force
    Allows overwriting an existing dataset at -Path. Without this switch, the script
    refuses to run if any dataset file already exists at the destination.

.EXAMPLE
    .\scripts\New-LabDataset.ps1 -Path "Z:\Project-A"

.EXAMPLE
    .\scripts\New-LabDataset.ps1 -Path "\\server\share\Project-A" -Force
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Path,

    [switch]$Force
)

$ErrorActionPreference = 'Stop'

# All content below is fabricated for lab testing: no real people, employers, companies,
# credentials, or confidential information. Domains use RFC 2606 reserved example domains.
$datasetFiles = [ordered]@{
    'control-clean.txt'        = @{
        TestPurpose = 'negative-control'
        Content     = @'
Lab Notes: Weekly Status Summary (Synthetic Control File)

This document is a synthetic control file used for data classification testing.
It intentionally contains no personal names, email addresses, phone numbers,
government identifiers, financial account numbers, or confidential business
information.

The quarterly maintenance window completed without incident. All scheduled
storage volumes were verified online, and no capacity alerts were triggered
during the review period. The team updated the shared runbook with the
latest operational checklist and archived the previous revision for reference.

This file exists purely as a negative control baseline for the ANF Agentic
Data Security Lab dataset. If a data classification scan flags this file as
containing sensitive or personal data, that result should be investigated
as a possible false positive, since no such data was intentionally included.
'@
    }
    'product-info.txt'         = @{
        TestPurpose = 'normal-business-data'
        Content     = @'
Product Overview: NimbusDrive Backup Appliance (Fictional Product)

NimbusDrive is a fictional backup appliance created for lab testing purposes.
It is not a real NetApp, Microsoft, or any other vendor product.

Key features (fictional):
- Up to 48 TB of usable synthetic capacity per appliance
- Simulated deduplication ratio of 4:1 for lab demonstration purposes
- Fictional support for NFS and SMB protocol testing
- Example tiering policy for moving cold synthetic data to object storage

This document contains ordinary, non-sensitive product information and is
intended to represent content that an AI agent could normally be permitted
to summarize for a general business audience.
'@
    }
    'public-announcement.txt'  = @{
        TestPurpose = 'public-information'
        Content     = @'
Public Announcement (Fictional): NimbusDrive 2.0 Preview

FOR IMMEDIATE RELEASE - SYNTHETIC LAB CONTENT

Example Corp (a fictional company created for this lab) today previewed
NimbusDrive 2.0, a fictional update to its synthetic backup appliance
product line. The preview highlighted simulated performance improvements
and an example integration with fictional cloud storage tiers.

This announcement is entirely fictional and was generated for the ANF
Agentic Data Security Lab. It does not describe a real product, company,
or event, and contains no personal or confidential information.
'@
    }
    'customers.csv'            = @{
        TestPurpose = 'pii-detection'
        Content     = @'
CustomerID,FirstName,LastName,Email,Phone,City,State
C-1001,Test,Testerson,test.testerson@example.com,555-0101,Springfield,IL
C-1002,Sample,Sampleton,sample.sampleton@example.net,555-0102,Rivertown,OH
C-1003,Demo,Demopoulos,demo.demopoulos@example.org,555-0103,Lakeside,MI
C-1004,Fictional,Franklin,fictional.franklin@example.com,555-0104,Hillview,TX
C-1005,Synthetic,Summers,synthetic.summers@example.net,555-0105,Oakdale,WA
C-1006,Placeholder,Patterson,placeholder.patterson@example.org,555-0106,Elmwood,GA
C-1007,Mock,Morrison,mock.morrison@example.com,555-0107,Brookfield,CO
C-1008,Dummy,Donovan,dummy.donovan@example.net,555-0108,Fairview,AZ
'@
    }
    'employees.csv'            = @{
        TestPurpose = 'employee-personal-data'
        Content     = @'
EmployeeID,Name,Email,Phone,Department,JobTitle
E-2001,Test Testerson,test.testerson@example.com,555-0201,Engineering,Lab Technician (Fictional)
E-2002,Sample Sampleton,sample.sampleton@example.net,555-0202,Operations,Synthetic Data Analyst (Fictional)
E-2003,Demo Demopoulos,demo.demopoulos@example.org,555-0203,Finance,Fictional Accounts Clerk
E-2004,Fictional Franklin,fictional.franklin@example.com,555-0204,Human Resources,Fictional HR Coordinator
E-2005,Synthetic Summers,synthetic.summers@example.net,555-0205,IT,Fictional Systems Administrator
E-2006,Placeholder Patterson,placeholder.patterson@example.org,555-0206,Sales,Fictional Account Representative
'@
    }
    'acquisition-plan.txt'     = @{
        TestPurpose = 'confidential-business-data-experiment'
        Content     = @'
SYNTHETIC LAB DATA
NOT REAL CONFIDENTIAL INFORMATION

Project Codename: Project Lighthouse (Fictional)

This document is entirely fictional and was generated for the ANF Agentic
Data Security Lab. It does not describe any real company, transaction, or
confidential business activity.

Fictional target company: Northwind Harbor Logistics (fictional, does not exist)
Fictional acquisition value: approximately 42 million USD (synthetic figure)
Fictional future announcement date: a date beyond the current lab testing period

Fictional business risks considered in this synthetic scenario:
- Simulated integration risk between fictional logistics platforms
- Simulated regulatory review timeline for a fictional transaction
- Simulated key-personnel retention risk at the fictional target company

The purpose of this file is to observe how NetApp Data Classification scans
and categorizes business-context language. No assumption is made in advance
about whether this file will be classified as confidential; the actual scan
result must be recorded separately in docs/testing/dataset-test-plan.md.
'@
    }
}

# Resolve/validate the destination path. Creating a directory is non-destructive,
# so this step always proceeds regardless of -Force.
if (Test-Path -LiteralPath $Path) {
    $destinationItem = Get-Item -LiteralPath $Path
    if (-not $destinationItem.PSIsContainer) {
        Write-Error "-Path '$Path' already exists and is not a directory."
        exit 1
    }
}
else {
    try {
        Write-Host "Creating destination directory: $Path"
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
    catch {
        Write-Error "Failed to create destination directory '$Path'. Verify the mapped drive or UNC share is reachable and writable. Details: $($_.Exception.Message)"
        exit 1
    }
}

# Refuse to silently overwrite an existing dataset.
$manifestFileName = 'manifest.json'
$allFileNames = @($datasetFiles.Keys) + $manifestFileName
$existingFileNames = @()
foreach ($name in $allFileNames) {
    $candidatePath = Join-Path -Path $Path -ChildPath $name
    if (Test-Path -LiteralPath $candidatePath) {
        $existingFileNames += $name
    }
}

if ($existingFileNames.Count -gt 0 -and -not $Force) {
    Write-Error "Dataset files already exist at '$Path': $($existingFileNames -join ', '). Re-run with -Force to regenerate."
    exit 1
}

Write-Host "Generating synthetic lab dataset at: $Path"
Write-Host ""

$summary = [System.Collections.Generic.List[object]]::new()

foreach ($name in $datasetFiles.Keys) {
    $filePath = Join-Path -Path $Path -ChildPath $name
    try {
        Set-Content -LiteralPath $filePath -Value $datasetFiles[$name].Content -Encoding utf8 -Force
    }
    catch {
        Write-Error "Failed to write '$filePath'. Details: $($_.Exception.Message)"
        exit 1
    }
    $fileSize = (Get-Item -LiteralPath $filePath).Length
    Write-Host ("  Created {0} ({1} bytes)" -f $name, $fileSize)
    $summary.Add([pscustomobject]@{
        File         = $name
        'Size'       = $fileSize
        'TestPurpose' = $datasetFiles[$name].TestPurpose
    })
}

# Build and write the manifest last, so it reflects only files that were successfully written.
$manifest = [ordered]@{
    dataset         = 'ANF Agentic Data Security Lab'
    version         = '0.1'
    synthetic       = $true
    generatedUtc    = (Get-Date).ToUniversalTime().ToString('o')
    generatorScript = 'scripts/New-LabDataset.ps1'
    files           = @(
        foreach ($name in $datasetFiles.Keys) {
            [ordered]@{
                file        = $name
                testPurpose = $datasetFiles[$name].TestPurpose
            }
        }
    )
}

$manifestPath = Join-Path -Path $Path -ChildPath $manifestFileName
try {
    $manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding utf8 -Force
}
catch {
    Write-Error "Failed to write manifest '$manifestPath'. Details: $($_.Exception.Message)"
    exit 1
}

$manifestSize = (Get-Item -LiteralPath $manifestPath).Length
Write-Host ("  Created {0} ({1} bytes)" -f $manifestFileName, $manifestSize)
$summary.Add([pscustomobject]@{
    File          = $manifestFileName
    'Size'        = $manifestSize
    'TestPurpose' = 'dataset-manifest'
})

Write-Host ""
Write-Host "Dataset summary:"
$summary | Format-Table -Property File, Size, TestPurpose -AutoSize

Write-Host ""
Write-Host "Done. All generated content is synthetic and safe for a public repository."
Write-Host "Next step: scan this dataset with NetApp Data Classification and record the actual results in docs/testing/dataset-test-plan.md."
