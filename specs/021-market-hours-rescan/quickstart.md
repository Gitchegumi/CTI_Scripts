# Quickstart: Forex Market Hours Rescan

## Validation Steps

1. Run the focused session-rule tests:

   ```powershell
   pytest src\tradegumi\tests\test_session_rules.py
   ```

2. Run command/rescan and scanner-related tests:

   ```powershell
   pytest src\tradegumi\tests\test_commands.py src\tradegumi\tests\test_main_market_data.py
   ```

3. Verify these forex boundary cases in tests:

   - Sunday 15:59 Central reports closed for forex instruments.
   - Sunday 16:00 Central / 17:00 Eastern reports open.
   - Sunday 21:40 Central reports open.
   - A normal weekday between the Sunday open and Friday close reports open.
   - Friday 15:59 Central reports open.
   - Friday 16:00 Central / 17:00 Eastern reports closed.
   - Saturday reports closed.
   - The same checks remain correct across daylight saving time.

4. Verify forced-rescan behavior with a fake execution client:

   - Available symbols remain available during the open forex trading week.
   - Symbol-specific unavailable results affect only those symbols.
   - Zero available symbols includes a clear reason distinguishing true forex market closure from account/instrument availability.

5. If dashboard or TypeScript state shapes change, run:

   ```powershell
   npm run build
   ```

6. Manually inspect runtime state after an API rescan in a local worker/API session:

   ```powershell
   Invoke-RestMethod -Method Post http://localhost:8199/api/action/rescan
   Invoke-RestMethod http://localhost:8199/api/data/loop_state
   Invoke-RestMethod http://localhost:8199/api/data/watchlist
   ```

## Expected Operator Outcome

During the forex trading week, including Sunday 21:40 Central, the dashboard and scan diagnostics should show forex markets as open. During the weekend break after Friday 16:00 Central and before Sunday 16:00 Central, they should show forex markets as closed. A forced rescan should refresh the watchlist and preserve available symbols during open forex hours instead of reporting the full configured symbol set as unavailable.
