# Repository Lineage: spring-petclinic-rest

## Data Movements

| Flow ID | From | To | Operation / Mechanism | Data Elements | Transformations | Confidence | Evidence |
|---|---|---|---|---|---|---|---|
| FL-001 | CMP-003 | CMP-001 | query owners / Spring Data JPA over JDBC | EL-003→EL-002; EL-006→EL-005; EL-009→EL-008; EL-012→EL-011; EL-015→EL-014; EL-018→EL-017 | none; rename | confirmed | EV-001, EV-002, EV-003, EV-042, EV-044, EV-017, EV-018, EV-035, EV-026, EV-033, EV-011 |
| FL-002 | CMP-001 | CMP-002 | return owner JSON response / HTTP JSON | EL-002→EL-001; EL-005→EL-004; EL-008→EL-007; EL-011→EL-010; EL-014→EL-013; EL-017→EL-016 | serialize | confirmed | EV-001, EV-002, EV-003, EV-042, EV-044, EV-017, EV-018, EV-035, EV-026, EV-033, EV-011 |
| FL-003 | CMP-002 | CMP-001 | receive owner JSON request / HTTP JSON | EL-004→EL-005; EL-007→EL-008; EL-010→EL-011; EL-013→EL-014; EL-016→EL-017 | deserialize | confirmed | EV-001, EV-002, EV-003, EV-042, EV-044, EV-017, EV-018, EV-035, EV-026, EV-033, EV-011 |
| FL-004 | CMP-001 | CMP-003 | save owners / Spring Data JPA over JDBC | EL-005→EL-006; EL-008→EL-009; EL-011→EL-012; EL-014→EL-015; EL-017→EL-018 | rename; none | confirmed | EV-001, EV-002, EV-003, EV-042, EV-044, EV-017, EV-018, EV-035, EV-026, EV-033, EV-011 |
| FL-005 | CMP-003 | CMP-001 | query pets / Spring Data JPA over JDBC | EL-021→EL-020; EL-024→EL-023; EL-027→EL-026; EL-030→EL-029; EL-033→EL-032 | none; rename | confirmed | EV-001, EV-002, EV-003, EV-042, EV-045, EV-019, EV-036, EV-026, EV-027, EV-034, EV-012 |
| FL-006 | CMP-001 | CMP-002 | return pet JSON response / HTTP JSON | EL-020→EL-019; EL-023→EL-022; EL-026→EL-025; EL-029→EL-028; EL-032→EL-031 | serialize | confirmed | EV-001, EV-002, EV-003, EV-042, EV-045, EV-019, EV-036, EV-026, EV-027, EV-034, EV-012 |
| FL-007 | CMP-002 | CMP-001 | receive pet JSON request / HTTP JSON | EL-022→EL-023; EL-025→EL-026; EL-028→EL-029; EL-031→EL-032 | deserialize | confirmed | EV-001, EV-002, EV-003, EV-042, EV-045, EV-019, EV-036, EV-026, EV-027, EV-034, EV-012 |
| FL-008 | CMP-001 | CMP-003 | save pets / Spring Data JPA over JDBC | EL-023→EL-024; EL-026→EL-027; EL-029→EL-030; EL-032→EL-033 | none; rename | confirmed | EV-001, EV-002, EV-003, EV-042, EV-045, EV-019, EV-036, EV-026, EV-027, EV-034, EV-012 |
| FL-009 | CMP-003 | CMP-001 | query types / Spring Data JPA over JDBC | EL-036→EL-035; EL-039→EL-038 | none | confirmed | EV-001, EV-002, EV-003, EV-042, EV-046, EV-020, EV-037, EV-028, EV-013 |
| FL-010 | CMP-001 | CMP-002 | return petType JSON response / HTTP JSON | EL-035→EL-034; EL-038→EL-037 | serialize | confirmed | EV-001, EV-002, EV-003, EV-042, EV-046, EV-020, EV-037, EV-028, EV-013 |
| FL-011 | CMP-002 | CMP-001 | receive petType JSON request / HTTP JSON | EL-037→EL-038 | deserialize | confirmed | EV-001, EV-002, EV-003, EV-042, EV-046, EV-020, EV-037, EV-028, EV-013 |
| FL-012 | CMP-001 | CMP-003 | save types / Spring Data JPA over JDBC | EL-038→EL-039 | none | confirmed | EV-001, EV-002, EV-003, EV-042, EV-046, EV-020, EV-037, EV-028, EV-013 |
| FL-013 | CMP-003 | CMP-001 | query specialties / Spring Data JPA over JDBC | EL-042→EL-041; EL-045→EL-044 | none | confirmed | EV-001, EV-002, EV-003, EV-042, EV-047, EV-021, EV-038, EV-029, EV-011 |
| FL-014 | CMP-001 | CMP-002 | return specialty JSON response / HTTP JSON | EL-041→EL-040; EL-044→EL-043 | serialize | confirmed | EV-001, EV-002, EV-003, EV-042, EV-047, EV-021, EV-038, EV-029, EV-011 |
| FL-015 | CMP-002 | CMP-001 | receive specialty JSON request / HTTP JSON | EL-043→EL-044 | deserialize | confirmed | EV-001, EV-002, EV-003, EV-042, EV-047, EV-021, EV-038, EV-029, EV-011 |
| FL-016 | CMP-001 | CMP-003 | save specialties / Spring Data JPA over JDBC | EL-044→EL-045 | none | confirmed | EV-001, EV-002, EV-003, EV-042, EV-047, EV-021, EV-038, EV-029, EV-011 |
| FL-017 | CMP-003 | CMP-001 | query vets / Spring Data JPA over JDBC | EL-048→EL-047; EL-051→EL-050; EL-054→EL-053; EL-057→EL-056; EL-045→EL-059 | none; rename | confirmed | EV-001, EV-002, EV-003, EV-042, EV-048, EV-022, EV-039, EV-030, EV-014 |
| FL-018 | CMP-001 | CMP-002 | return vet JSON response / HTTP JSON | EL-047→EL-046; EL-050→EL-049; EL-053→EL-052; EL-056→EL-055; EL-059→EL-058 | serialize | confirmed | EV-001, EV-002, EV-003, EV-042, EV-048, EV-022, EV-039, EV-030, EV-014 |
| FL-019 | CMP-002 | CMP-001 | receive vet JSON request / HTTP JSON | EL-049→EL-050; EL-052→EL-053; EL-055→EL-056; EL-058→EL-059 | deserialize | confirmed | EV-001, EV-002, EV-003, EV-042, EV-048, EV-022, EV-039, EV-030, EV-014 |
| FL-020 | CMP-001 | CMP-003 | save vets / Spring Data JPA over JDBC | EL-050→EL-051; EL-053→EL-054; EL-056→EL-057; EL-059→EL-045 | rename | confirmed | EV-001, EV-002, EV-003, EV-042, EV-048, EV-022, EV-039, EV-030, EV-014 |
| FL-021 | CMP-003 | CMP-001 | query visits / Spring Data JPA over JDBC | EL-063→EL-062; EL-066→EL-065; EL-069→EL-068; EL-072→EL-071 | none; rename | confirmed | EV-001, EV-002, EV-003, EV-042, EV-049, EV-023, EV-040, EV-026, EV-031, EV-015 |
| FL-022 | CMP-001 | CMP-002 | return visit JSON response / HTTP JSON | EL-062→EL-061; EL-065→EL-064; EL-068→EL-067; EL-071→EL-070 | serialize | confirmed | EV-001, EV-002, EV-003, EV-042, EV-049, EV-023, EV-040, EV-026, EV-031, EV-015 |
| FL-023 | CMP-002 | CMP-001 | receive visit JSON request / HTTP JSON | EL-064→EL-065; EL-067→EL-068; EL-070→EL-071 | deserialize | confirmed | EV-001, EV-002, EV-003, EV-042, EV-049, EV-023, EV-040, EV-026, EV-031, EV-015 |
| FL-024 | CMP-001 | CMP-003 | save visits / Spring Data JPA over JDBC | EL-065→EL-066; EL-068→EL-069; EL-071→EL-072 | rename; none | confirmed | EV-001, EV-002, EV-003, EV-042, EV-049, EV-023, EV-040, EV-026, EV-031, EV-015 |
| FL-025 | CMP-002 | CMP-001 | receive user JSON request / HTTP JSON | EL-073→EL-074; EL-076→EL-077; EL-079→EL-080; EL-082→EL-083 | deserialize | confirmed | EV-001, EV-002, EV-003, EV-043, EV-050, EV-024, EV-025, EV-041, EV-032, EV-016 |
| FL-026 | CMP-001 | CMP-003 | save users and roles / Spring Data JPA over JDBC | EL-074→EL-075; EL-077→EL-078; EL-080→EL-081; EL-083→EL-084 | none; enrich | confirmed | EV-001, EV-002, EV-003, EV-043, EV-050, EV-024, EV-025, EV-041, EV-032, EV-016 |

## Boundary Contracts for Agent 2

| Contract ID | Direction | Mechanism | Normalized Locator | Data Elements | Confidence | Issues |
|---|---|---|---|---|---|---|
| CTR-001 | inbound | http | http://localhost:9966/petclinic/api/owners | EL-001, EL-004, EL-007, EL-010, EL-013, EL-016 | confirmed | — |
| CTR-002 | inbound | http | http://localhost:9966/petclinic/api/owners/{ownerId} | EL-001, EL-004, EL-007, EL-010, EL-013, EL-016 | confirmed | — |
| CTR-003 | inbound | http | http://localhost:9966/petclinic/api/v2/owners | EL-001, EL-004, EL-007, EL-010, EL-013, EL-016 | confirmed | — |
| CTR-004 | inbound | http | http://localhost:9966/petclinic/api/owners/{ownerId}/pets | EL-019, EL-022, EL-025, EL-028, EL-031 | confirmed | — |
| CTR-005 | inbound | http | http://localhost:9966/petclinic/api/owners/{ownerId}/pets/{petId} | EL-019, EL-022, EL-025, EL-028, EL-031 | confirmed | — |
| CTR-006 | inbound | http | http://localhost:9966/petclinic/api/pets | EL-019, EL-022, EL-025, EL-028, EL-031 | confirmed | — |
| CTR-007 | inbound | http | http://localhost:9966/petclinic/api/pets/{petId} | EL-019, EL-022, EL-025, EL-028, EL-031 | confirmed | — |
| CTR-008 | inbound | http | http://localhost:9966/petclinic/api/v2/pets | EL-019, EL-022, EL-025, EL-028, EL-031 | confirmed | — |
| CTR-009 | inbound | http | http://localhost:9966/petclinic/api/owners/{ownerId}/pets/{petId}/visits | EL-061, EL-064, EL-067, EL-070 | confirmed | — |
| CTR-010 | inbound | http | http://localhost:9966/petclinic/api/visits | EL-061, EL-064, EL-067, EL-070 | confirmed | — |
| CTR-011 | inbound | http | http://localhost:9966/petclinic/api/visits/{visitId} | EL-061, EL-064, EL-067, EL-070 | confirmed | — |
| CTR-012 | inbound | http | http://localhost:9966/petclinic/api/pettypes | EL-034, EL-037 | confirmed | — |
| CTR-013 | inbound | http | http://localhost:9966/petclinic/api/pettypes/{petTypeId} | EL-034, EL-037 | confirmed | — |
| CTR-014 | inbound | http | http://localhost:9966/petclinic/api/specialties | EL-040, EL-043 | confirmed | — |
| CTR-015 | inbound | http | http://localhost:9966/petclinic/api/specialties/{specialtyId} | EL-040, EL-043 | confirmed | — |
| CTR-016 | inbound | http | http://localhost:9966/petclinic/api/vets | EL-046, EL-049, EL-052, EL-055, EL-058 | confirmed | — |
| CTR-017 | inbound | http | http://localhost:9966/petclinic/api/vets/{vetId} | EL-046, EL-049, EL-052, EL-055, EL-058 | confirmed | — |
| CTR-018 | inbound | http | http://localhost:9966/petclinic/api/users | EL-073, EL-076, EL-079, EL-082 | confirmed | — |
| CTR-019 | inbound | database | jdbc:h2:mem:petclinic/owners | EL-003, EL-006, EL-009, EL-012, EL-015, EL-018 | confirmed | — |
| CTR-020 | outbound | database | jdbc:h2:mem:petclinic/owners | EL-003, EL-006, EL-009, EL-012, EL-015, EL-018 | confirmed | — |
| CTR-021 | inbound | database | jdbc:h2:mem:petclinic/pets | EL-021, EL-024, EL-027, EL-030, EL-033 | confirmed | — |
| CTR-022 | outbound | database | jdbc:h2:mem:petclinic/pets | EL-021, EL-024, EL-027, EL-030, EL-033 | confirmed | — |
| CTR-023 | inbound | database | jdbc:h2:mem:petclinic/types | EL-036, EL-039 | confirmed | — |
| CTR-024 | outbound | database | jdbc:h2:mem:petclinic/types | EL-036, EL-039 | confirmed | — |
| CTR-025 | inbound | database | jdbc:h2:mem:petclinic/specialties | EL-042, EL-045 | confirmed | — |
| CTR-026 | outbound | database | jdbc:h2:mem:petclinic/specialties | EL-042, EL-045 | confirmed | — |
| CTR-027 | inbound | database | jdbc:h2:mem:petclinic/vets | EL-048, EL-051, EL-054, EL-057, EL-045 | confirmed | — |
| CTR-028 | outbound | database | jdbc:h2:mem:petclinic/vets | EL-048, EL-051, EL-054, EL-057, EL-045 | confirmed | — |
| CTR-029 | inbound | database | jdbc:h2:mem:petclinic/visits | EL-063, EL-066, EL-069, EL-072 | confirmed | — |
| CTR-030 | outbound | database | jdbc:h2:mem:petclinic/visits | EL-063, EL-066, EL-069, EL-072 | confirmed | — |
| CTR-031 | outbound | database | jdbc:h2:mem:petclinic/users+roles | EL-075, EL-078, EL-081, EL-084 | confirmed | — |

## End-to-End Paths Within This Repository

| Path ID | Path | Data Elements | Confidence | Issues |
|---|---|---|---|---|
| PATH-001 | CMP-003 → FL-001 → CMP-001 → FL-002 → CMP-002 | EL-003, EL-006, EL-009, EL-012, EL-015, EL-018, EL-002, EL-005, EL-008, EL-011, EL-014, EL-017, EL-001, EL-004, EL-007, EL-010, EL-013, EL-016 | confirmed | — |
| PATH-002 | CMP-002 → FL-003 → CMP-001 → FL-004 → CMP-003 | EL-004, EL-007, EL-010, EL-013, EL-016, EL-005, EL-008, EL-011, EL-014, EL-017, EL-006, EL-009, EL-012, EL-015, EL-018 | confirmed | — |
| PATH-003 | CMP-003 → FL-005 → CMP-001 → FL-006 → CMP-002 | EL-021, EL-024, EL-027, EL-030, EL-033, EL-020, EL-023, EL-026, EL-029, EL-032, EL-019, EL-022, EL-025, EL-028, EL-031 | confirmed | — |
| PATH-004 | CMP-002 → FL-007 → CMP-001 → FL-008 → CMP-003 | EL-022, EL-025, EL-028, EL-031, EL-023, EL-026, EL-029, EL-032, EL-024, EL-027, EL-030, EL-033 | confirmed | — |
| PATH-005 | CMP-003 → FL-009 → CMP-001 → FL-010 → CMP-002 | EL-036, EL-039, EL-035, EL-038, EL-034, EL-037 | confirmed | — |
| PATH-006 | CMP-002 → FL-011 → CMP-001 → FL-012 → CMP-003 | EL-037, EL-038, EL-039 | confirmed | — |
| PATH-007 | CMP-003 → FL-013 → CMP-001 → FL-014 → CMP-002 | EL-042, EL-045, EL-041, EL-044, EL-040, EL-043 | confirmed | — |
| PATH-008 | CMP-002 → FL-015 → CMP-001 → FL-016 → CMP-003 | EL-043, EL-044, EL-045 | confirmed | — |
| PATH-009 | CMP-003 → FL-017 → CMP-001 → FL-018 → CMP-002 | EL-048, EL-051, EL-054, EL-057, EL-045, EL-047, EL-050, EL-053, EL-056, EL-059, EL-046, EL-049, EL-052, EL-055, EL-058 | confirmed | — |
| PATH-010 | CMP-002 → FL-019 → CMP-001 → FL-020 → CMP-003 | EL-049, EL-052, EL-055, EL-058, EL-050, EL-053, EL-056, EL-059, EL-051, EL-054, EL-057, EL-045 | confirmed | — |
| PATH-011 | CMP-003 → FL-021 → CMP-001 → FL-022 → CMP-002 | EL-063, EL-066, EL-069, EL-072, EL-062, EL-065, EL-068, EL-071, EL-061, EL-064, EL-067, EL-070 | confirmed | — |
| PATH-012 | CMP-002 → FL-023 → CMP-001 → FL-024 → CMP-003 | EL-064, EL-067, EL-070, EL-065, EL-068, EL-071, EL-066, EL-069, EL-072 | confirmed | — |
| PATH-013 | CMP-002 → FL-025 → CMP-001 → FL-026 → CMP-003 | EL-073, EL-076, EL-079, EL-082, EL-074, EL-077, EL-080, EL-083, EL-075, EL-078, EL-081, EL-084 | confirmed | — |

## Unresolved Issues

| Issue ID | Type | Severity | Description | Related IDs | Evidence |
|---|---|---|---|---|---|
