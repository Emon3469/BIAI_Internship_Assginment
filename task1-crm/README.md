# Sample data for the CRM task

All people and phone numbers here are fictional. There are 20 enquiries in Bangla, Banglish and English from WhatsApp, Facebook, the website and phone call notes.

Some are real sales enquiries. Some are not (for example support issues, spam, and a job seeker). Think about how your CRM should handle each kind.

## Processing

Run the complete CPU-only backend from the project root:

```powershell
python main.py --process-only
```

The workflow uses NFKC/whitespace normalization, Bangla/Banglish detection,
rule-based intent classification, phone normalization, and conservative
sender/message duplicate matching. It intentionally does not invent missing
contact details. Results are written to `outputs/task1/`.

The classifier is deterministic and does not require an API key, model
download, or GPU. The FastAPI endpoint `POST /api/crm/classify` accepts the
same fields for frontend or channel integrations.
