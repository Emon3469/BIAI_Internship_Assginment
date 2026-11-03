# Sample data for the Corporate Leads Pipeline task

All companies, people, emails and phone numbers here are fictional. This is not real BIAI client data.

- `corporate-leads.csv`: 25 corporate leads with stage, deal value, last contact, next follow-up and notes.
- `stage-definitions.md`: the five pipeline stages and the two end stages.

Reference date: 1 November 2026. Some follow-ups are overdue on purpose.
The data is messy on purpose. Real CRM data is messy too, so clean it up as you build.

## Processing

Run the complete CPU-only backend from the project root:

```powershell
python main.py --process-only
```

The pipeline standardizes column names and contact formats, detects explicit
and high-confidence duplicates, validates dates and stages, flags missing
fields, reports IQR deal-value outliers without changing legitimate values,
and calculates overdue follow-ups relative to 1 November 2026. Missing
contact data remains blank and is surfaced as a manual follow-up action.
Results are written to `outputs/task2/`.

FastAPI endpoints under `/api/pipeline` expose cleaned leads, overdue leads,
data issues, duplicates, stage filters, and analytics for a frontend.
