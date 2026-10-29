# Project test findings — 27 October 2026

**Checklist: 38/41 passed; 3 cases failed, exposing 4 application defects.** Existing suite: **50/54 passed; 1 failure and 3 errors; no skipped tests** when Oracle integration was enabled.

Tests ran against the current working tree, including its pre-existing uncommitted changes and new Delete Song page. No production source, existing tests, or original song files were edited by this test run.

## Execution and scope

- Real Oracle Database Free 23 in a separate disposable Docker container, `songs-checklist-test-20261027`, bound to localhost port 1522. The existing database on port 1521 was not targeted.
- Streamlit 1.61.1 AppTest exercised real page widgets and production services against Oracle; normal business operations were not mocked. White-box cases deliberately injected failures or synchronized concurrent operations.
- All 41 checklist IDs were executed. Browser verification used a separate Streamlit process on port 8503 and confirmed chart rendering, chart values, and the Example `is = 3` tooltip.
- CSV validation checked the exact payload supplied to the real download widget for all three scopes. The browser export button was also clicked; a completed operating-system download file was not independently located, so disk delivery is not claimed as verified.
- Publication-year and location input bounds were inspected as rendered widget constraints; invalid year service calls were also executed. These are automated equivalents of the manual boundary checks, not a claim that every invalid keystroke was manually entered in a browser.
- The original nine named sample files were used. The recently added `sample_songs/tester.txt` was deliberately excluded from the original baseline. No additional lyric fixtures were required.
- Baseline: 9 songs, 66 stanzas, 376 lines, 2,379 word occurrences, 454 unique words, average word length 3.91, average words per line 6.33.
- Initial run took 70.697 seconds. Two harness assertions were corrected and those cases rechecked in 3.331 seconds: BB12 now checks original token content independently of its existing label typo; BB21 validates actual chart specifications rather than an obsolete internal element type. No application code was changed to obtain passing results.

## Confirmed application defects

### 1. Restore leaves cached word-search results stale — BB24

Reproduction: search `love` with all nine songs; in the same session restore a backup excluding Whitney Houston's song; return to Search without submitting a new search. **Expected:** clear or refresh results. **Observed:** 25 cached results remain although live Oracle returns 12. Restore regenerates IDs, so the old results cannot retrieve their original contexts. The successful restore path does not clear search session state.

[Restore handler](</Users/roilan01/university/database-workshop-songs/pages/7_backup_restore.py:93>).

### 2. Same-title/artist songs disappear from two selectors — BB26

Reproduction: upload `example.txt` as Example/Test Artist with an empty album and again with album Other Album. **Expected:** both selectable. **Observed:** Word Index and Statistics each offer one Example entry; All Songs correctly offers two IDs. The selectors use title/artist strings as dictionary keys, so the second entry replaces the first.

[Word Index selector](</Users/roilan01/university/database-workshop-songs/pages/3_word_index.py:27>); [Statistics selector](</Users/roilan01/university/database-workshop-songs/pages/6_statistics.py:32>).

### 3. Concurrent uploads bypass duplicate-song protection — WB14

Reproduction: run two real uploads of `example.txt` with identical title/artist/album, pausing both immediately after their duplicate checks until both are ready. **Expected:** one succeeds and the other is rejected. **Observed:** both committed, producing two different song IDs for the same metadata. The check runs separately from insertion, and the schema has no matching unique constraint.

[Duplicate check before insertion](</Users/roilan01/university/database-workshop-songs/src/song_service.py:47>).

### 4. Concurrent member removal permits an empty group — WB14

Reproduction: create a group containing love and hallelujah; start two removals, pausing both after they read the two-member group. **Expected:** at least one member remains. **Observed:** both removals returned True and the group retained zero members. The count/check and delete have no group-level serialization.

[Membership check and delete](</Users/roilan01/university/database-workshop-songs/src/group_service.py:141>).

### Minor UI issue

The word-position result labels the preserved original token **Original Work**. The value itself is correct. [Label](</Users/roilan01/university/database-workshop-songs/pages/2_search.py:364>).

## Existing suite failures

Three errors originate in malformed test fixtures, not reproduced production group failures:

- `test_create_group_with_first_word_is_atomic`: mock returns `(42)`, an integer, instead of `(42,)`.
- `test_adding_same_word_to_group_is_friendly_error`: same integer-versus-one-element-tuple issue.
- `test_renaming_group_to_existing_name_is_friendly_error`: mock returns `(99)` instead of `(99,)`.

The corresponding real Oracle group behavior passed BB15–BB17 and WB08. These existing tests were left unchanged.

The remaining failure is `test_no_oneoff_publication_year_script_in_submission`: `add_publication_year_check.sql` still exists, contrary to that static submission check. This is a repository/package check, not a runtime database failure.

The opt-in real Oracle deletion/cascade test passed. The original default run skipped that opt-in test; the final Oracle-enabled run had no skips.

## Checklist results

| ID | Result | Evidence |
|---|---|---|
| BB01 | PASS | All ten current pages rendered against an empty schema; empty metadata and word searches handled. |
| BB02 | PASS | example.txt upload: 2 stanzas / 4 lines / 16 words; love is matches increased from 2 to 3 after Hallelujah upload. |
| BB03 | PASS | All nine files uploaded through the real upload page; every per-song count matched the checklist. |
| BB04 | PASS | Blank/whitespace title, blank artist, and missing file rejected; table counts unchanged. |
| BB05 | PASS | UI bounds are 1000–2026; real uploads at both bounds succeeded; service rejected 999 and 2027. |
| BB06 | PASS | Exact, case/space variants, and year-only duplicate uploads rejected; complete table snapshot unchanged. |
| BB07 | PASS | Upload controls disabled after success; Upload Another Song cleared fields/file and enabled submission. |
| BB08 | PASS | Example text reconstructed exactly apart from trailing newline in service, Search, and All Songs. |
| BB09 | PASS | Partial/case-insensitive and combined metadata searches, year filters, and SQL-looking text behaved correctly. |
| BB10 | PASS | love, LOVE, and spaced love returned 25 occurrences; absent word returned none. |
| BB11 | PASS | All 39 Hallelujah occurrences navigated forward and backward; boundary buttons, reset, and empty-input clearing verified. |
| BB12 | PASS | All three location modes returned the correct text/word. Original token air, is displayed under the typo Original Work. |
| BB13 | PASS | Missing locations handled; position widgets have minimum 1; first/last Example context contains only valid neighboring lines. |
| BB14 | PASS | Full/Example/Queen indexes contain 2379/16/367 rows; exact CSV payload, columns, ordering, and rendered download control verified. |
| BB15 | PASS | Two-word group produced 64 occurrences; intersecting with Hallelujah produced 40. |
| BB16 | PASS | Missing group name/member, unknown word, duplicate membership, and case-variant group name rejected. |
| BB17 | PASS | Group rename/description, member removal, final-member protection, confirmation, and deletion verified. |
| BB18 | PASS | Phrase matches: let it be=41, always love you=11, lover to lover=15; matching songs and context correct. |
| BB19 | PASS | go go returned line 12 positions 3–4 and 4–5; trouble mother returned no cross-line match. |
| BB20 | PASS | Punctuation/case-normalized phrase matched 3 times; invalid/duplicate definitions rejected; deletion preserved songs/words. |
| BB21 | PASS | Database totals and averages matched. Three Example chart specifications, data and tooltip fields checked; charts and tooltip also viewed in browser. |
| BB22 | PASS | UI XML export/restore round trip preserved all eight tables semantically, including remapped relationships; extra song removed; confirmation enforced. |
| BB23 | PASS | Malformed, wrong-root, and missing-section backups rejected; complete pre-restore table snapshots preserved. |
| BB24 | FAIL | FAIL: same Streamlit session retained 25 cached love results after restoring a collection with only 12; cached IDs no longer exist. |
| BB25 | PASS | Dedicated Oracle container actually stopped/restarted. Pages and upload reported failure; original test data survived; subsequent upload succeeded. |
| BB26 | FAIL | FAIL: two Example songs with different albums collapse to one selector option in Word Index and Statistics; All Songs correctly offers both IDs. |
| WB01 | PASS | Example parser produced positions 1–16; love at (line,position,song position)=(3,1,8),(4,2,14). |
| WB02 | PASS | Example stanza transition correctly changed (global line,stanza,local line) from (2,1,2) to (3,2,1). |
| WB03 | PASS | Adele line 9 has 10 words; face& is original token at position 6 and that follows at position 7. |
| WB04 | PASS | Queen contains 21 normalized don't occurrences; straight apostrophes and original capitalization preserved. |
| WB05 | PASS | Oracle has 454 dictionary words and 2379 occurrences; all 25 love occurrences share one word ID. |
| WB06 | PASS | Upload-time refresh and phrase creation agree on two overlapping matches and rejection of cross-line candidates. |
| WB07 | PASS | Injected failures after eight occurrence inserts and during phrase refresh rolled back the entire upload, including new vocabulary. |
| WB08 | PASS | Injected failures between group/membership inserts and after phrase occurrence insert left no partial data. |
| WB09 | PASS | Five existing controlled connection-failure tests passed, including commit failure; separate actual Oracle UPDATE/rollback preserved snapshot. |
| WB10 | PASS | New Oracle IDs differed after restore while all logical content/relationships matched; invalid late reference rolled back deletions and inserts. |
| WB11 | PASS | Oracle rejected duplicate word/membership/case-variant group, invalid FK, zero position, and duplicate song position; original rows unchanged. |
| WB12 | PASS | Group/phrase child rows cascaded; song deletion cascaded within a rolled-back transaction; vocabulary and original data preserved. |
| WB13 | PASS | Fifth connection timed out near five seconds while four were held; release enabled immediate successful reuse. |
| WB14 | FAIL | FAIL: synchronized real transactions committed two identical songs; concurrent removals both succeeded and left zero group members. |
| WB15 | PASS | Upload temporary files were removed after both success and an injected database failure; files were directed under sample_songs during tests. |

## Evidence and rerunning

- [Machine-readable results and detailed failure traces](</Users/roilan01/university/database-workshop-songs/tests/checklist_results.json>)
- [Complete checklist runner](</Users/roilan01/university/database-workshop-songs/tests/run_manual_checklist.py>)
- [Test support and isolated-database guard](</Users/roilan01/university/database-workshop-songs/tests/checklist_support.py>)
- [Initial checklist execution log](</Users/roilan01/university/database-workshop-songs/tests/checklist_run.log>)
- [Corrected harness recheck log](</Users/roilan01/university/database-workshop-songs/tests/checklist_recheck.log>)
- [Existing suite with real Oracle enabled](</Users/roilan01/university/database-workshop-songs/tests/existing_suite_oracle_results.log>)
- [Baseline backup generated by the tests](</Users/roilan01/university/database-workshop-songs/tests/checklist_baseline.xml>)

From the repository root, create a fresh disposable container (the runner replaces all data on its guarded test port):

```sh
docker run -d --name songs-checklist-test-20261027 \
  -p 127.0.0.1:1522:1521 \
  -e ORACLE_PASSWORD=songsproject \
  -e APP_USER=concordance -e APP_USER_PASSWORD=songsproject \
  gvenzl/oracle-free:23-slim
# Wait for Oracle and the concordance user to be ready, then:
RUN_MANUAL_CHECKLIST=1 ORACLE_PORT=1522 PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python -m tests.run_manual_checklist
RUN_ORACLE_INTEGRATION=1 ORACLE_PORT=1522 PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python -m unittest discover -s tests -v
# Remove only this disposable environment when finished:
docker rm -f -v songs-checklist-test-20261027
```

A nonzero checklist exit is expected until the four defects above are fixed. The separate test container and browser server used for this report were removed/stopped after verification; rerunning requires creating the test environment again.

## Browser evidence

![Example chart and tooltip](/Users/roilan01/university/database-workshop-songs/tests/checklist_chart.png)
