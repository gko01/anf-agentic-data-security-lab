# Sample Dataset — ANF Agentic Data Security Lab

This directory documents the synthetic test dataset used by this lab to validate
NetApp Data Classification scanning and, later, the DSPM policy engine. See the
main [README.md](../README.md) for the overall project design; this page covers
only the dataset and its generator.

The dataset itself is **not** committed to this repository (see
[Repository Structure](../README.md#12-repository-structure)). Instead, a
reproducible PowerShell script generates it on demand at a destination you
control, such as an Azure NetApp Files SMB share.

## Why this dataset exists

The lab needs a small, controlled set of files with known, documented *intent*
so that NetApp Data Classification scan results can be compared against an
expectation rather than guessed at. Each file targets a specific test signal:
a negative control, ordinary business data, public information, synthetic PII,
synthetic employee data, and a fictional confidential-business scenario.

All content is fabricated. No real people, employers, companies, credentials,
or confidential information are included anywhere in the generator or its
output. See [docs/testing/dataset-test-plan.md](../docs/testing/dataset-test-plan.md)
for how scan results should be recorded once observed.

## Generated files

| File | Test purpose | What it is for |
|---|---|---|
| `control-clean.txt` | `negative-control` | Ordinary synthetic text with no intentionally planted names, emails, phone numbers, or confidential content. Baseline for comparison. |
| `product-info.txt` | `normal-business-data` | Fictional product information. Expected to support an `ALLOW`-style scenario later. |
| `public-announcement.txt` | `public-information` | Fictional public announcement. Represents content an agent would normally be allowed to summarize. |
| `customers.csv` | `pii-detection` | Synthetic customer records (name, email, phone, city, state) using obviously fictional names and RFC 2606 reserved example domains. Used to observe PII detection. |
| `employees.csv` | `employee-personal-data` | Synthetic employee records (name, email, phone, department, job title). Used to observe personal/employment-data detection. |
| `acquisition-plan.txt` | `confidential-business-data-experiment` | Entirely fictional acquisition scenario, clearly labeled `SYNTHETIC LAB DATA / NOT REAL CONFIDENTIAL INFORMATION`. Used to observe how business-sensitive language is classified. |
| `manifest.json` | `dataset-manifest` | Machine-readable description of the dataset: which files exist and their intended test purpose. |

Expected classification behavior is **not** guaranteed by this documentation.
NetApp Data Classification's actual output must be observed and recorded, not
assumed in advance.

## Generating the dataset

The generator script is [scripts/New-LabDataset.ps1](../scripts/New-LabDataset.ps1).
It only writes files to the path you give it — it does not deploy or configure
Azure NetApp Files, mount shares, or call any NetApp or Microsoft API.

### Mapped-drive example

```powershell
.\scripts\New-LabDataset.ps1 -Path "Z:\Project-A"
```

### UNC-path example

```powershell
.\scripts\New-LabDataset.ps1 -Path "\\server\share\Project-A"
```

### Regenerating with `-Force`

By default, the script refuses to overwrite a dataset that already exists at
the destination. To intentionally regenerate it:

```powershell
.\scripts\New-LabDataset.ps1 -Path "Z:\Project-A" -Force
```

After generation, the script prints a summary table of each file's name, size,
and test purpose.

## Expected directory structure after generation

```text
Project-A/
|-- control-clean.txt
|-- product-info.txt
|-- public-announcement.txt
|-- customers.csv
|-- employees.csv
|-- acquisition-plan.txt
`-- manifest.json
```

## Next step

Once the dataset is generated on an ANF share, scan it with NetApp Data
Classification and record the actual results in
[docs/testing/dataset-test-plan.md](../docs/testing/dataset-test-plan.md).
