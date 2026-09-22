# Getting sample annual reports

The app parses **company** and **year** from the filename, so save PDFs as
`YEAR_Company.pdf`, e.g. `2024_Apple.pdf`, into `data/raw_pdfs/`.

## Free sources (US filings — 10-K)

Annual reports (Form 10-K) are free from the SEC's EDGAR system:

- Apple:     https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000320193&type=10-K
- Microsoft: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000789019&type=10-K
- Tesla:     https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001318605&type=10-K

Open the latest 10-K, download the primary document as PDF (or print-to-PDF),
and rename it, e.g. `2024_Apple.pdf`.

## UK alternative

For UK companies, annual reports are on Companies House
(https://find-and-update.company-information.service.gov.uk/) or the company's
investor-relations page. Same naming convention applies.

## Then

Either drop the files in `data/raw_pdfs/` and run the batch ingester:

```bash
python -m ingestion.ingest_documents
```

…or upload them one at a time in the Streamlit **Upload** tab.
