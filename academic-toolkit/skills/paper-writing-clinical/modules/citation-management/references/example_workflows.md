# Example Workflows

Four end-to-end worked examples: building a bibliography for a paper, converting a
list of DOIs, cleaning an existing BibTeX file, and finding and citing seminal papers.

## Example Workflows

### Example 1: Building a Bibliography for a Paper

```bash
# Step 1: Find key papers on your topic
# (Google Scholar: export BibTeX directly — GS results carry no DOI field)
python scripts/search_google_scholar.py "transformer neural networks" \
  --year-start 2017 \
  --limit 50 \
  --format bibtex \
  --output transformers_gs.bib

python scripts/search_pubmed.py "deep learning medical imaging" \
  --date-start 2020 \
  --limit 50 \
  --output medical_dl_pm.json

# Step 2: Pull DOI/PMID identifiers out of the PubMed JSON into a text file
# (one identifier per line — extract_metadata.py identifies each line; it
#  cannot parse the JSON file directly)
python -c "import json; d = json.load(open('medical_dl_pm.json')); print('\n'.join(r.get('doi') or r.get('pmid','') for r in d['results']))" \
  | grep -v '^$' > medical_ids.txt

# Step 3: Extract metadata from the identifier file
python scripts/extract_metadata.py \
  --input medical_ids.txt \
  --output medical.bib

# Step 4: Add specific papers you already know
python scripts/doi_to_bibtex.py 10.1038/s41586-021-03819-2 >> specific.bib
python scripts/doi_to_bibtex.py 10.1126/science.aam9317 >> specific.bib

# Step 5: Combine all BibTeX files
cat transformers_gs.bib medical.bib specific.bib > combined.bib

# Step 6: Format and deduplicate
python scripts/format_bibtex.py combined.bib \
  --deduplicate \
  --sort year \
  --descending \
  --output references.bib

# Step 7: Validate (auto-fix is not implemented — the validator reports only)
python scripts/validate_citations.py references.bib \
  --report validation.json \
  --verbose

# Step 8: Review any issues
cat validation.json | grep -A 3 '"errors"'

# Step 9: Use in LaTeX
# \bibliography{references}
```

### Example 2: Converting a List of DOIs

```bash
# You have a text file with DOIs (one per line)
# dois.txt contains:
# 10.1038/s41586-021-03819-2
# 10.1126/science.aam9317
# 10.1016/j.cell.2023.01.001

# Convert all to BibTeX
python scripts/doi_to_bibtex.py --input dois.txt --output references.bib

# Validate the result
python scripts/validate_citations.py references.bib --verbose
```

### Example 3: Cleaning an Existing BibTeX File

```bash
# You have a messy BibTeX file from various sources
# Clean it up systematically

# Step 1: Format and standardize
python scripts/format_bibtex.py messy_references.bib \
  --output step1_formatted.bib

# Step 2: Remove duplicates
python scripts/format_bibtex.py step1_formatted.bib \
  --deduplicate \
  --output step2_deduplicated.bib

# Step 3: Validate (auto-fix is not implemented — the validator reports only)
python scripts/validate_citations.py step2_deduplicated.bib \
  --report step3_validation.json

# Step 4: Fix any reported issues by hand, then sort by year
python scripts/format_bibtex.py step2_deduplicated.bib \
  --sort year \
  --descending \
  --output clean_references.bib

# Step 5: Final validation report
python scripts/validate_citations.py clean_references.bib \
  --report final_validation.json \
  --verbose

# Review report
cat final_validation.json
```

### Example 4: Finding and Citing Seminal Papers

```bash
# Find highly cited papers on a topic (each result includes its citation count)
python scripts/search_google_scholar.py "AlphaFold protein structure" \
  --year-start 2020 \
  --year-end 2024 \
  --sort-by citations \
  --limit 20 \
  --output alphafold_seminal.json

# Convert to BibTeX — reliable path: the search script exports BibTeX itself
python scripts/search_google_scholar.py "AlphaFold protein structure" \
  --year-start 2020 \
  --year-end 2024 \
  --sort-by citations \
  --limit 20 \
  --format bibtex \
  --output alphafold_refs.bib

# Alternative two-step: pull the result URLs out of the JSON (one per line),
# then feed the file to extract_metadata.py. Expect partial success —
# extract_metadata.py resolves only URLs that embed a DOI, PMID, or arXiv ID.
python -c "import json; d = json.load(open('alphafold_seminal.json')); print('\n'.join(r.get('url','') for r in d['results']))" \
  | grep -v '^$' > alphafold_ids.txt
python scripts/extract_metadata.py \
  --input alphafold_ids.txt \
  --output alphafold_refs.bib

# The BibTeX file now contains the most influential papers
```
