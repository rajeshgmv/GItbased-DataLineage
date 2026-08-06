# Cross-Repository Data Lineage

Repositories analyzed: Chroma_db_reader, crypto-kaka-rag, json_reader_test, spring-petclinic-rest
Repository inputs: 4
Cross-repository connections: 1

## Application-to-Application Lineage

| Flow ID | Source Application | Target Application | Mechanism | Operation | Shared Boundary | Data Summary | Confidence | Issues |
|---|---|---|---|---|---|---|---|---|
| HL-001 | Chroma_db_reader | json_reader_test | file | write → read | `file://{working_directory}/chroma-export.json` ⇢ `file:///Users/guttikonda/Desktop/training%20docs/chroma_db_reader/chroma-export.json` | `records[].document`, `records[].metadata.asset`, `records[].metadata.time` | partial | `Chroma_db_reader:ISS-002`; `Chroma_db_reader:ISS-003`; Agent 2: source locator is runtime-relative while target locator is absolute; matching is supported by the common filename, complementary operations, and compatible JSON schema, but absolute-path equality is unproven and the source metadata object's nested fields are incomplete. |

## Detailed Data Flow

| Detail ID | Flow ID | Source Application | Source Contract / Flow | Source Data Element(s) | Source Type | Source Raw / Normalized Locator | Mechanism | Operation | Transformation Chain | Target Application | Target Contract / Flow | Target Data Element | Target Type | Target Raw / Normalized Locator | Confidence | Evidence | Issues |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DF-001 | HL-001 | Chroma_db_reader | `Chroma_db_reader:CTR-002` / `Chroma_db_reader:FL-002` | `Chroma_db_reader:EL-021: records[].document` | unknown | `chroma-export.json` / `file://{working_directory}/chroma-export.json` | file | write → read | `serialize` (`document` JSON key emitted to redirected output) → UTF-8 JSON read/deserialization | json_reader_test | `json_reader_test:CTR-001` / `json_reader_test:FL-001` | `json_reader_test:EL-003: records[].document` | string | `/Users/guttikonda/Desktop/training docs/chroma_db_reader/chroma-export.json` / `file:///Users/guttikonda/Desktop/training%20docs/chroma_db_reader/chroma-export.json` | partial | `Chroma_db_reader:EV-014`, `Chroma_db_reader:EV-018`, `json_reader_test:EV-006`, `json_reader_test:EV-007`, `json_reader_test:EV-008` | `Chroma_db_reader:ISS-002`; `Chroma_db_reader:ISS-003`; Agent 2: non-exact relative/absolute locator match. |
| DF-002 | HL-001 | Chroma_db_reader | `Chroma_db_reader:CTR-002` / `Chroma_db_reader:FL-002` | `Chroma_db_reader:EL-022: records[].metadata` | object | `chroma-export.json` / `file://{working_directory}/chroma-export.json` | file | write → read | `aggregate` (`json_group_object` over non-`chroma:%` keys) → `serialize` as the `metadata` JSON object → UTF-8 JSON read → access `metadata.asset` | json_reader_test | `json_reader_test:CTR-001` / `json_reader_test:FL-001` | `json_reader_test:EL-001: records[].metadata.asset` | unknown | `/Users/guttikonda/Desktop/training docs/chroma_db_reader/chroma-export.json` / `file:///Users/guttikonda/Desktop/training%20docs/chroma_db_reader/chroma-export.json` | partial | `Chroma_db_reader:EV-006`, `Chroma_db_reader:EV-007`, `Chroma_db_reader:EV-008`, `Chroma_db_reader:EV-009`, `Chroma_db_reader:EV-014`, `Chroma_db_reader:EV-018`, `json_reader_test:EV-004`, `json_reader_test:EV-005`, `json_reader_test:EV-008` | `Chroma_db_reader:ISS-002`; `Chroma_db_reader:ISS-003`; Agent 2: non-exact locator and source metadata schema does not explicitly expose the nested `asset` path. |
| DF-003 | HL-001 | Chroma_db_reader | `Chroma_db_reader:CTR-002` / `Chroma_db_reader:FL-002` | `Chroma_db_reader:EL-022: records[].metadata` | object | `chroma-export.json` / `file://{working_directory}/chroma-export.json` | file | write → read | `aggregate` (`json_group_object` over non-`chroma:%` keys) → `serialize` as the `metadata` JSON object → UTF-8 JSON read → access `metadata.time` | json_reader_test | `json_reader_test:CTR-001` / `json_reader_test:FL-001` | `json_reader_test:EL-002: records[].metadata.time` | unknown | `/Users/guttikonda/Desktop/training docs/chroma_db_reader/chroma-export.json` / `file:///Users/guttikonda/Desktop/training%20docs/chroma_db_reader/chroma-export.json` | partial | `Chroma_db_reader:EV-006`, `Chroma_db_reader:EV-007`, `Chroma_db_reader:EV-008`, `Chroma_db_reader:EV-009`, `Chroma_db_reader:EV-014`, `Chroma_db_reader:EV-018`, `json_reader_test:EV-005`, `json_reader_test:EV-008` | `Chroma_db_reader:ISS-002`; `Chroma_db_reader:ISS-003`; Agent 2: non-exact locator and source metadata schema does not explicitly expose the nested `time` path. |

## Application Flow Diagram

```mermaid
flowchart LR
  APP_001["Chroma_db_reader"]
  APP_002["json_reader_test"]
  APP_001 -->|"HL-001 · file · chroma-export.json"| APP_002
```
