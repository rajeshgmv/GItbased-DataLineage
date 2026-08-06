# Repository Lineage: Chroma_db_reader

## Data Movements

| Flow ID | From | To | Operation / Mechanism | Data Elements | Transformations | Confidence | Evidence |
|---|---|---|---|---|---|---|---|
| FL-001 | CMP-002 | CMP-001 | read Chroma records and aggregate them into JSON records / SQLite CLI read-only query | EL-001→EL-015; EL-003→EL-016; EL-004+EL-005→EL-017; EL-004+EL-005+EL-006+EL-007+EL-008→EL-018 | rename; aggregate | partial | EV-004, EV-005, EV-006, EV-007, EV-008, EV-009, EV-010, EV-011, EV-012, EV-013, EV-014, EV-015, EV-016, EV-017 |
| FL-002 | CMP-001 | CMP-003 | write aggregated JSON array to chroma-export.json / process standard-output redirection | EL-015→EL-019; EL-016→EL-020; EL-017→EL-021; EL-018→EL-022 | serialize | partial | EV-013, EV-014, EV-016, EV-018 |

## Boundary Contracts for Agent 2

| Contract ID | Direction | Mechanism | Normalized Locator | Data Elements | Confidence | Issues |
|---|---|---|---|---|---|---|
| CTR-001 | inbound | database | sqlite:///Users/guttikonda/Desktop/training%20docs/crypto-kafka-rag-project/crypto_chroma_db | EL-001, EL-002, EL-003, EL-004, EL-005, EL-006, EL-007, EL-008, EL-009, EL-010, EL-011, EL-012, EL-013, EL-014 | partial | ISS-001, ISS-003 |
| CTR-002 | outbound | file | file://{working_directory}/chroma-export.json | EL-019, EL-020, EL-021, EL-022 | partial | ISS-002, ISS-003 |

## End-to-End Paths Within This Repository

| Path ID | Path | Data Elements | Confidence | Issues |
|---|---|---|---|---|
| PATH-001 | CMP-002 → FL-001 → CMP-001 → FL-002 → CMP-003 | EL-001, EL-003, EL-004, EL-005, EL-006, EL-007, EL-008, EL-015, EL-016, EL-017, EL-018, EL-019, EL-020, EL-021, EL-022 | partial | ISS-001, ISS-002, ISS-003 |

## Unresolved Issues

| Issue ID | Type | Severity | Description | Related IDs | Evidence |
|---|---|---|---|---|---|
| ISS-001 | missing_endpoint | medium | The input constant is an absolute path, but runtime file-system state determines whether it is used directly as the SQLite file or resolved as a directory containing chroma.sqlite3; the context does not prove which locator is active. | CMP-002, CTR-001, FL-001, PATH-001 | EV-003, EV-016 |
| ISS-002 | missing_endpoint | medium | The output filename is proven, but its absolute location depends on the process working directory, which is not present in the context. | CMP-003, CTR-002, FL-002, PATH-001 | EV-003, EV-016, EV-018 |
| ISS-003 | missing_schema | low | The context contains the SQL column names and exact JSON mappings but no SQLite DDL or declared field types, so source column types and the scalar output types remain unknown. | CTR-001, CTR-002, FL-001, FL-002, PATH-001 | EV-004, EV-005, EV-006, EV-007, EV-008, EV-009, EV-010, EV-011 |
