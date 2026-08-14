# Lazarus automated-test evidence

This folder contains regression evidence for the final suite of 123 tests covering 41 user stories. Each user story has one main case, one validation case, and one alternate case.

## Current Green execution

- Test suite: `CURRENT_GREEN_123_TESTS.py.txt`
- Output: `CURRENT_GREEN_123_OUTPUT.txt`
- Result: 123 tests ran and all passed (`OK`).
- Application version: the downloaded Lazarus repository supplied for the final update.

## Historical Red execution

- Test suite: `HISTORICAL_RED_123_TESTS.py.txt`
- Output: `HISTORICAL_RED_123_OUTPUT.txt`
- Result: 123 tests ran, with 84 failures and 18 errors.
- Application version: historical snapshot `e0d973e65f82d7243255cef51246b3e87d4fa316`.

The same 123-test acceptance suite was used for both executions. The historical output demonstrates that many expected behaviours were unavailable or incompatible in the earlier snapshot, while the current output demonstrates that the suite passes against the final implementation. This is historical regression evidence supporting the Red–Green–Refactor discussion; it is not presented as a complete chronological record proving that every production component was originally written only after its test.

## Numbering change

The previous 42-story/126-test version was replaced after the reconstruction and decryption requirements were merged. The combined requirement is now US27: the file is automatically reconstructed and decrypted for the user. The final numbering therefore runs from US1 to US41, with 123 tests in total.
