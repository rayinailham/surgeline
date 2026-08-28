# SurgeLine — SCHEMA (dikunci di P4)

> STUB. Diisi & **dikunci** di fase P4. Sebelum itu jangan mengandalkan isinya.

Akan mendefinisikan, final dan tidak berubah setelah P4:
- **Record** dari generator/loader: field, tipe, mana `required`, natural key `external_ref`.
- **Tabel `jobs`**: kolom, tipe, `UNIQUE(external_ref)`, state machine
  `pending → claimed → ok | failed | dead`, kolom `confirmation`, `attempts`, `claimed_at`,
  `worker_id`, `last_error`, timestamp.
- **Tabel `attempts`** (audit tiap percobaan): `external_ref`, `worker_id`, `started_at`,
  `outcome`, `error`, `confirmation`.
- **File hasil**: `run.json` (metrik run), lokasi `data/<run_id>/`.
- Aturan transisi + indeks.
