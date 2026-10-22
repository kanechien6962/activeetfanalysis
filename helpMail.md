**Subject: GitHub Actions schedule events are not triggering**

Hello GitHub Support,

My public repository `kanechien6962/activeetfanalysis` has GitHub Actions workflows that run successfully when triggered manually using `workflow_dispatch`, but scheduled runs are never created.

I have verified the following:

- The repository is public and is not a fork.
- The default branch is `main`.
- The workflow file is committed to `.github/workflows/fetch_etf.yml`.
- The workflow API reports its state as `active`.
- Actions permissions are set to allow all actions and reusable workflows.
- I tested a minimal workflow containing only a `schedule` trigger and a simple shell command.
- I changed the cron expression, committed the changes to `main`, and disabled and re-enabled the workflow.
- The GitHub Actions API shows only `workflow_dispatch` runs. No runs with the `schedule` event have been created.

Workflow ID: `390254540`

Could you please investigate whether scheduled events are being generated for this repository, or whether there is an account-level or scheduler-side issue?

Thank you.

I can’t see GitHub’s internal scheduler logs from the repo, but based on the workflow configuration and repo metadata, there is no sign of an account-level or repository-level block.

The workflow is valid and active:

```yaml name=.github/workflows/fetch_etf.yml url=https://github.com/kanechien6962/activeetfanalysis/blob/main/.github/workflows/fetch_etf.yml#L3-L7
on:
  schedule:
    - cron: "7 10 * * 1-5"
  workflow_dispatch:
```

What this means:

- `schedule` is valid GitHub Actions syntax.
- The cron is in UTC.
- `7 10 * * 1-5` means: 10:07 UTC, Monday through Friday.
- In Taiwan time, that is roughly 18:07 local time.
- GitHub does not use your local timezone for scheduled workflows; it always evaluates cron in UTC.

Important detail:
- Scheduled workflows only run when the workflow file exists on the default branch and the workflow is enabled.
- If the workflow was added/changed recently, or the cron window has not occurred since the last change, GitHub will not create a `schedule` run yet.
- The fact that you only see `workflow_dispatch` runs is not by itself evidence of a scheduler outage.

Most likely explanations:
- The cron has simply not matched since the last workflow update on `main`.
- The repo was not on the default branch at the relevant schedule time.
- The schedule was tested during a time window that had not yet occurred in UTC.

Recommended validation:
- Confirm the workflow file is definitely present on the default branch (`main`) and has not been modified recently.
- For a quick test, use a near-term cron with a short interval, for example:
  - `*/5 * * * *` to test every 5 minutes in UTC
- Keep it on `main` and wait for the next matching time.
- If you still get no `schedule` runs after a valid near-term test, then it would be worth escalating as a scheduler/platform issue.

I do not see evidence here that this is a GitHub account-level or scheduler-side problem. The current repo configuration looks consistent with normal GitHub Actions behavior.