# Latest complete test run

Follow-up after the label and mock-fixture fixes: `tests.test_database_service` and `tests.test_schema_contract` were rerun with `SINGLE_USER_TESTS=1`. Of 32 selected tests, 30 passed, 1 concurrency test was skipped, and the migration-file absence assertion remained the only failure. All three previous mock errors now pass. Four malformed one-column mock rows were corrected, including one in a previously passing test. The Search label is now **Original Word**. See [follow-up log](/Users/roilan01/university/database-workshop-songs/tests/label_and_fixture_verification.log). The complete-run results below describe the earlier run before these fixes; the Oracle integration suites were not rerun for this follow-up.

Executed: 2026-10-27T11:38:31.911498+02:00

Scope: One active user session, with sequential operations; concurrency tests are out of scope.

Real Oracle on isolated port 1522; existing database on port 1521 was not used.

| Suite | Tests | Passed | Failures | Errors | Skipped |
|---|---:|---:|---:|---:|---:|
| Full checklist | 41 | 40 | 0 | 0 | 1 |
| Discovered regression suite | 64 | 59 | 1 | 3 | 1 |
| Restore integration verification | 3 | 3 | 0 | 0 | 0 |
| Selector integration verification | 5 | 5 | 0 | 0 | 0 |

The dedicated restore and selector suites repeat some checklist coverage and add targeted verification; suite counts are executions, not a count of unique scenarios.

## Findings

All 40 applicable checklist cases passed using the original nine files under `sample_songs/` and real Oracle. The restore-cache and same-name song-selector fixes passed again. Sequential duplicate uploads, final-member removal protection, and the Oracle song-deletion regression passed.

Across the four suites: 107 passed, 1 failed, 3 errored, and 2 concurrency cases were skipped. The remaining unsuccessful cases are:

| Case | Finding |
|---|---|
| `test_create_group_with_first_word_is_atomic` | The mock returns `(42)`, an integer, instead of a database row `(42,)`; indexing the result raises `TypeError: 'int' object is not subscriptable`. |
| `test_adding_same_word_to_group_is_friendly_error` | The same malformed `(42)` fixture causes the same TypeError before duplicate-membership handling can be tested. |
| `test_renaming_group_to_existing_name_is_friendly_error` | The mock returns `(99)` rather than `(99,)`, causing the same TypeError before the expected validation error. |
| `test_no_oneoff_publication_year_script_in_submission` | `add_publication_year_check.sql` exists, but the static test requires that file to be absent. This is a submission-file check, not a runtime database failure. |

The three mock errors do not establish application defects; the corresponding group behavior passed the real-Oracle checklist. Their fixtures and the submission-file failure were left intact for this run.

Single-user scope means one active session executing operations sequentially, including across browser tabs. Concurrent uploads/member removal and concurrent transaction-isolation tests were explicitly skipped, not counted as passing. Existing concurrency behavior was not changed.

Reproduce with the disposable Oracle container running: `RUN_MANUAL_CHECKLIST=1 ORACLE_PORT=1522 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m tests.run_all_tests --single-user`.

This run changed only test scripts and generated evidence under `tests/`; no production code was changed. The disposable Oracle container and volume were removed after the run.

## Failures and logs

- [Full checklist](/Users/roilan01/university/database-workshop-songs/tests/all_checklist.log): OK (skipped=1).
  - Out of scope: `test_WB14_concurrency_races (__main__.Checklist.test_WB14_concurrency_races) ... skipped 'Out of scope: one active user session with sequential operations'`
- [Discovered regression suite](/Users/roilan01/university/database-workshop-songs/tests/all_regressions.log): FAILED (failures=1, errors=3, skipped=1).
  - `test_adding_same_word_to_group_is_friendly_error (test_database_service.BusinessTransactionTests.test_adding_same_word_to_group_is_friendly_error)`
  - `test_create_group_with_first_word_is_atomic (test_database_service.BusinessTransactionTests.test_create_group_with_first_word_is_atomic)`
  - `test_renaming_group_to_existing_name_is_friendly_error (test_database_service.BusinessTransactionTests.test_renaming_group_to_existing_name_is_friendly_error)`
  - `test_no_oneoff_publication_year_script_in_submission (test_schema_contract.SchemaContractTests.test_no_oneoff_publication_year_script_in_submission)`
  - Out of scope: `test_concurrent_operations_have_independent_transactions (test_database_service.DatabaseServiceTests.test_concurrent_operations_have_independent_transactions) ... skipped 'Out of scope: one active user session with sequential operations'`
- [Restore integration verification](/Users/roilan01/university/database-workshop-songs/tests/all_restore.log): OK.
- [Selector integration verification](/Users/roilan01/university/database-workshop-songs/tests/all_selectors.log): OK.

## Current checklist evidence

**test_BB24_search_state_after_restore: PASS**

```json
{
  "cached_count": 0,
  "live_count": 12,
  "cached_song_ids": [
    203,
    204,
    206,
    209,
    210
  ],
  "live_song_ids": [
    212,
    213,
    217,
    218
  ]
}
```

**test_BB26_same_name_different_albums: PASS**

```json
{
  "selector_options": {
    "pages/3_word_index.py": [
      "Example \u2014 Test Artist \u2014 No album (ID: 230)",
      "Example \u2014 Test Artist \u2014 Other Album (ID: 239)"
    ],
    "pages/6_statistics.py": [
      "Example \u2014 Test Artist \u2014 No album (ID: 230)",
      "Example \u2014 Test Artist \u2014 Other Album (ID: 239)"
    ],
    "pages/8_all_songs.py": [
      "Example \u2014 Test Artist (ID: 230)",
      "Example \u2014 Test Artist (ID: 239)"
    ]
  }
}
```

**test_WB14_concurrency_races: SKIP**

Out of scope: one active user session with sequential operations

