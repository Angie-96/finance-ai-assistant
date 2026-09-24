---
description: Run the same checks as CI (lint, typegen, typecheck, unit tests, build) before pushing
---

Run these in order and stop at the first failure, reporting the exact error output:

1. `npm run lint`
2. `npx next typegen`
3. `npx tsc --noEmit`
4. `npm run test`
5. `npm run build`

If everything passes, say so briefly. If something fails, fix the root cause (don't suppress the check) and re-run from the step that failed.
