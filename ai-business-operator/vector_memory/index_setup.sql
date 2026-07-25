-- ---------------------------------------------------------------------------
-- Vector index tuning. Run AFTER the first bulk load, not before.
--
-- IVFFlat builds its clusters from data that already exists — an index created on
-- an empty table gives poor recall until rebuilt. `001_init.sql` creates one for
-- convenience; this file is how you fix it once there are real rows.
-- ---------------------------------------------------------------------------

-- Rule of thumb: lists ~= sqrt(row_count), clamped to [10, 1000].
-- Check the current count first:
--   SELECT count(*) FROM memory_records WHERE embedding IS NOT NULL;

DROP INDEX IF EXISTS idx_memory_embedding;

CREATE INDEX idx_memory_embedding ON memory_records
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Recall/latency trade-off at query time. Higher probes = better recall, slower.
-- Set per session, not globally:
--   SET ivfflat.probes = 10;

ANALYZE memory_records;

-- Supporting index for the filtered path — recall() always narrows by
-- embedding_model and expiry before the vector scan.
CREATE INDEX IF NOT EXISTS idx_memory_live
    ON memory_records (embedding_model, category, project_id)
    WHERE embedding IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Re-index after changing EMBEDDING_MODEL. Old-model rows are excluded from
-- recall() automatically (it filters on embedding_model), so they are inert
-- rather than wrong — but they still occupy space:
--
--   DELETE FROM memory_records WHERE embedding_model = '<old-model>';
--
-- Or re-embed them, which is preferable when the memory is worth keeping.
-- ---------------------------------------------------------------------------
