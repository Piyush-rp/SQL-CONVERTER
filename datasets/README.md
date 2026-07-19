# datasets/

Raw SQL data files used to seed demo/test databases - kept separate from
`scripts/` so the actual data is plain, editable SQL rather than buried in
Python string constants. `scripts/seed_demo_data.py` loads `demo/schema.sql`
and `demo/seed_data.sql` from here to build a ready-to-query SQLite file.

Want different demo data? Edit the `.sql` files directly - no code changes
needed.
