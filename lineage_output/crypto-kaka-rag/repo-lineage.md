# Repository Lineage: crypto-kaka-rag

## Data Movements

| Flow ID | From | To | Operation / Mechanism | Data Elements | Transformations | Confidence | Evidence |
|---|---|---|---|---|---|---|---|
| FL-001 | CMP-001 | CMP-002 | GET simple price request / HTTP GET query parameters | EL-008→EL-001; EL-009→EL-002; EL-010→EL-003; EL-011→EL-004 | none | confirmed | EV-002, EV-003, EV-004 |
| FL-002 | CMP-002 | CMP-001 | Receive successful simple price response / HTTP JSON response | EL-005→EL-013; EL-006→EL-014; EL-007→EL-015 | cast | confirmed | EV-004, EV-005 |
| FL-003 | CMP-001 | CMP-003 | Publish crypto tick / Kafka JSON UTF-8 | EL-012→EL-026; EL-013→EL-027; EL-014→EL-028; EL-015→EL-029; EL-016→EL-030 | serialize | confirmed | EV-001, EV-005, EV-006 |
| FL-004 | CMP-003 | CMP-001 | Consume crypto tick / Kafka JSON UTF-8 | EL-026→EL-017; EL-027→EL-018; EL-028→EL-019; EL-029→EL-020; EL-030→EL-021; EL-031→EL-022 | deserialize; none | confirmed | EV-007, EV-008, EV-009 |
| FL-005 | CMP-001 | CMP-004 | Insert market insight / Chroma collection.add | EL-017+EL-021+EL-018+EL-019+EL-020→EL-032; EL-017→EL-033; EL-021→EL-034; EL-021+EL-022→EL-035 | derive; none; rename | confirmed | EV-009, EV-010, EV-011 |
| FL-006 | CMP-004 | CMP-001 | Query top five matching documents / Chroma collection.query | EL-032→EL-024 | aggregate | confirmed | EV-012, EV-013 |
| FL-007 | CMP-001 | CMP-005 | Invoke llama3.1 / LangChain ChatOllama | EL-024+EL-023→EL-037 | derive | confirmed | EV-014, EV-015 |
| FL-008 | CMP-005 | CMP-001 | Receive model response / LangChain ChatOllama | EL-038→EL-025 | none | confirmed | EV-015 |

## Boundary Contracts for Agent 2

| Contract ID | Direction | Mechanism | Normalized Locator | Data Elements | Confidence | Issues |
|---|---|---|---|---|---|---|
| CTR-001 | outbound | http | https://api.coingecko.com/api/v3/simple/price | EL-001, EL-002, EL-003, EL-004, EL-005, EL-006, EL-007 | confirmed | — |
| CTR-002 | outbound | kafka | kafka://localhost:9092/crypto-ticks | EL-026, EL-027, EL-028, EL-029, EL-030 | confirmed | — |
| CTR-003 | inbound | kafka | kafka://localhost:9092/crypto-ticks | EL-026, EL-027, EL-028, EL-029, EL-030, EL-031 | confirmed | — |
| CTR-004 | outbound | database | chroma://repo/crypto-kaka-rag/chroma_db/market_insights | EL-032, EL-033, EL-034, EL-035 | confirmed | — |
| CTR-005 | inbound | database | chroma://repo/crypto-kaka-rag/chroma_db/market_insights | EL-032, EL-036 | confirmed | — |
| CTR-006 | outbound | other | http://127.0.0.1:11434/models/llama3.1:latest | EL-037, EL-038 | confirmed | — |

## End-to-End Paths Within This Repository

| Path ID | Path | Data Elements | Confidence | Issues |
|---|---|---|---|---|
| PATH-001 | CMP-002 → FL-002 → CMP-001 → FL-003 → CMP-003 | EL-005, EL-006, EL-007, EL-026, EL-027, EL-028, EL-029, EL-030 | confirmed | — |
| PATH-002 | CMP-003 → FL-004 → CMP-001 → FL-005 → CMP-004 | EL-026, EL-027, EL-028, EL-029, EL-030, EL-031, EL-032, EL-033, EL-034, EL-035 | confirmed | — |
| PATH-003 | CMP-002 → FL-002 → CMP-001 → FL-003 → CMP-003 → FL-004 → CMP-001 → FL-005 → CMP-004 | EL-005, EL-006, EL-007, EL-026, EL-027, EL-028, EL-029, EL-030, EL-032, EL-033, EL-034, EL-035 | confirmed | — |
| PATH-004 | CMP-004 → FL-006 → CMP-001 → FL-007 → CMP-005 | EL-032, EL-024, EL-023, EL-037 | confirmed | — |

## Unresolved Issues

| Issue ID | Type | Severity | Description | Related IDs | Evidence |
|---|---|---|---|---|---|
