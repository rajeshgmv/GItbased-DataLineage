# Repository Lineage: Chroma_db_reader

## Data Movements

| Flow ID | From | To | Operation / Mechanism | Data Elements | Transformations | Confidence | Evidence |
|---|---|---|---|---|---|---|---|
| FL-001 | CMP-002 | CMP-001 | read and aggregate Chroma records / sqlite3 read-only SQL | EL-001→EL-008; EL-002→EL-009; EL-003+EL-004→EL-010; EL-003+EL-004+EL-005+EL-006+EL-007→EL-011 | rename; none; aggregate | partial | EV-001, EV-002, EV-004, EV-005 |
| FL-002 | CMP-001 | CMP-003 | write JSON export / SQLite JSON functions redirected to file | EL-008→EL-012; EL-009→EL-013; EL-010→EL-014; EL-011→EL-015 | serialize | partial | EV-001, EV-003, EV-004, EV-005 |

## Boundary Contracts for Agent 2

| Contract ID | Direction | Mechanism | Normalized Locator | Data Elements | Confidence | Issues |
|---|---|---|---|---|---|---|
| CTR-001 | inbound | database | sqlite:////users/guttikonda/desktop/training docs/crypto-kafka-rag-project/crypto_chroma_db/chroma.sqlite3 | EL-001, EL-002, EL-003, EL-004, EL-005, EL-006, EL-007 | partial | ISS-001 |
| CTR-002 | outbound | file | file://repo/chroma_db_reader/chroma-export.json | EL-012, EL-013, EL-014, EL-015 | partial | ISS-001 |

## End-to-End Paths Within This Repository

| Path ID | Path | Data Elements | Confidence | Issues |
|---|---|---|---|---|
| PATH-001 | CMP-002 → FL-001 → CMP-001 → FL-002 → CMP-003 | EL-001, EL-002, EL-003, EL-004, EL-005, EL-006, EL-007, EL-012, EL-013, EL-014, EL-015 | partial | ISS-001 |

## Unresolved Issues

| Issue ID | Type | Severity | Description | Related IDs | Evidence |
|---|---|---|---|---|---|
| ISS-001 | incomplete_mapping | medium | Metadata keys are selected dynamically from embedding_metadata and keys beginning with chroma: are excluded, so the exact exported metadata field names and per-key types cannot be enumerated from this context. | CTR-001, CTR-002, FL-001, FL-002, PATH-001 | EV-002, EV-003 |
