# Repository Lineage: json_reader_test

## Data Movements

| Flow ID | From | To | Operation / Mechanism | Data Elements | Transformations | Confidence | Evidence |
|---|---|---|---|---|---|---|---|
| FL-001 | CMP-002 | CMP-001 | read and extract BTC rows / UTF-8 JSON array | EL-001+EL-002→EL-004; EL-003→EL-005 | filter; parse | confirmed | EV-001, EV-002, EV-003, EV-005 |
| FL-002 | CMP-001 | CMP-003 | write BTC price rows / UTF-8 CSV | EL-004→EL-006; EL-005→EL-007 | serialize | confirmed | EV-001, EV-004, EV-005 |

## Boundary Contracts for Agent 2

| Contract ID | Direction | Mechanism | Normalized Locator | Data Elements | Confidence | Issues |
|---|---|---|---|---|---|---|
| CTR-001 | inbound | file | file:///Users/guttikonda/Desktop/training docs/chroma_db_reader/chroma-export.json | EL-001, EL-002, EL-003 | confirmed | — |
| CTR-002 | outbound | file | file:///Users/guttikonda/Desktop/training docs/json_reader/output/btc_prices.csv | EL-006, EL-007 | confirmed | — |

## End-to-End Paths Within This Repository

| Path ID | Path | Data Elements | Confidence | Issues |
|---|---|---|---|---|
| PATH-001 | CMP-002 → FL-001 → CMP-001 → FL-002 → CMP-003 | EL-001, EL-002, EL-003, EL-006, EL-007 | confirmed | — |

## Unresolved Issues

| Issue ID | Type | Severity | Description | Related IDs | Evidence |
|---|---|---|---|---|---|
