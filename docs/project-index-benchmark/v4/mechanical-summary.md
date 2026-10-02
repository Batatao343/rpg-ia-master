# SPEC-175 v4 mechanical aggregation

This is the mechanical aggregation only. The semantic `resolved` scores and final mandatory/selective/remove decision remain pending Sol. The `sufficient localization gain` clause is also reserved for Sol. v1, v2, v3, and v4/aborted are explicitly excluded.

## Integrity and run validation

- Canonical ground-truth SHA-256: `1f5ec3ce3b235271d7a2cb0e02d3fd9fdf57326554dbde9e4f2714dee63f9af3`; matches the commitment.
- Revealed ground-truth file SHA-256: `1194c5cd6fc23c7bcd1c9a67e802dfc636094370e9711c9c002d23137fc3a3d6`; matches the committed sealed-file hash. Commitment file hash: `5e2ab0c5d00eb8f3394de279dd81beaa658fd5f8ca09e8342d6ce917ddb1ceac`.
- Attestation self-hash is valid: `1434a5c3d2054ce819537ed93883586c1fcdc33dde5b2ee774975db528d91e8c`. Preregistration hash matches: `99be09f43b0299a9b88e9a5fa25676b4d2a0f73472e0954dca386dcd1bb03408`.
- Source-tree hash matches the manifest: `b3171bcf014f5d9104a8223854709d5e3b1420092ea5b73af347d8cd618a76cd`. Project-index graph hash matches the manifest: `a30ab6f3ced9b09662c5ba3eee3df7f8c019e292c6705bd10a3171e6e53b2e07`.
- All four session prompt files match their attested and session-recorded prompt hashes. The attested shared prompt hash is `dadf5eb4a66f77e0d1e42dc7f90fbda52e6a528d151a8a61018c0b899e7e3bb4`; condition hashes are A `05b5351299d44822930d8d23afaaff3cd970d35bf99951374c236bd772dfe6b2` and B `93e20291884ee919a00ed1a3ac24dd3c98ed1235957b03f3f2aee7a858d9def6`.
- Four complete sessions used `gpt-5.6-terra` at high effort. Orders match the attestation: A1 ascending, A2 descending, B1 descending, B2 ascending. A has no index trace; every B task's first trace operation is `index:query`.
- Across 32 observations, trace operation counts and summed `source_bytes` match both stored usage and result fields. Every task is within 12 discovery calls, 50,000 source bytes, and 300 seconds.

Final session-file SHA-256 values:

| Session | SHA-256 |
| --- | --- |
| a1-v4 | `6053d3dd19e9b42d172e095856b362bcb734f33bfe0c672a9ced1e2710e2bf3e` |
| a2-v4 | `e188443fcc62b0a719350a9236f06ed67624596fd60df2b6ebc8185cfeb4da48` |
| b1-v4 | `b4bc3d129a431b9d74b791742caaf1345222e617da157bcb9c9c1d347295d9dd` |
| b2-v4 | `32ff7481906cd57aabfd275ac5fdc63a6ed511853fb851c1f8064597324644e8` |

## Metrics

Localization is a ground-truth core file among the first three reported implementation files. Irrelevant implementation files are reported files outside the task's core files; tests are excluded. Test recall is the fraction of ground-truth test files selected, after stripping any `::test_name` suffix. Means and medians use all 16 observations per condition; even-count medians average the two middle values.

| Metric | A | B |
| --- | ---: | ---: |
| Localization hits | 15/16 | 15/16 |
| Irrelevant implementation files, total | 10 | 9 |
| Irrelevant implementation files, mean | 0.625 | 0.5625 |
| Relevant test recall, mean | 0.5833 | 0.4167 |
| Discovery calls, median | 4 | 4.5 |
| Source bytes read, median | 25,142 | 10,115.5 |
| Wall seconds, median | 17.9655 | 28.419 |

Per-task averages across two replicates and the preregistered cost-win rule (B must reduce calls or bytes, with no more than 10% worsening in the other dimension):

| Task | A calls | B calls | A bytes | B bytes | Cost win |
| --- | ---: | ---: | ---: | ---: | --- |
| B01 | 4 | 6 | 18,053 | 20,020 | No |
| B02 | 2.5 | 2.5 | 37,970.5 | 11,634 | Yes |
| B03 | 3 | 4 | 21,064.5 | 8,280.5 | No |
| B04 | 5.5 | 4.5 | 18,563 | 10,732.5 | Yes |
| B05 | 2 | 4.5 | 31,158.5 | 12,107 | No |
| B06 | 3 | 4 | 34,829 | 5,558 | No |
| B07 | 4 | 7 | 37,819.5 | 17,171 | No |
| B08 | 6 | 7.5 | 13,482.5 | 11,464 | No |

There are 2/8 cost wins: B02 and B04. The global 20% criterion fails: B's median bytes fall 59.77%, but median calls rise 12.5%, exceeding the allowed 10% worsening. No semantic `resolved` scoring or final product-index decision is made here.
