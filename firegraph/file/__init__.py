# PROMPT (kept for traceability of edits in this package):
#   "optimize the ParquetMaster class"
# Scope of that change: firegraph/file/parquet.py (lazy handle, atomic IO,
# return-fix on `receive`, skip-existing, robust crawl). Public API unchanged.

# Constants
CHUNK_SIZE = 7 * 1024 * 1024  # 9MB
BUCKET_NAME = "bestbrain"  # Change to your GCS bucket name
OUTPUT_FOLDER = "model_graph/train_data/json/go_term/"