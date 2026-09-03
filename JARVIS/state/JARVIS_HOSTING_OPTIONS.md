# Running JARVIS for free — an honest options review

Status: **research only, nothing built.** Slow track, not a priority.
Written 2026-08-30.

Nothing here evades a usage limit, a paid tier or an account restriction
(D-005). Options that only work by dodging quotas or rotating accounts were
discarded on sight; none of the survivors below depend on that.

---

## What I could and could not verify

I read primary documentation, not blog posts. Two doc sites publish their
own source on GitHub, so I read that source directly:

- GitHub Actions — `github/docs`, files cited by path below.
- Cloudflare Workers — `cloudflare/cloudflare-docs`.
- Oracle — `oracle.com/cloud/free` and its FAQ page.

**I could not reach** Microsoft Learn, PythonAnywhere, Render, Fly.io or
Railway from this container — the network blocked them. So I state **no**
limit, price or free-tier claim for those. If you want them assessed, that
has to happen from your PC. I am not going to guess from memory.

One fact I did confirm about your setup: **`veer7710/signals` is a public
repository**, default branch `main`. That matters more than anything else
below, and it cuts both ways.

---

## 1. What can actually run persistently for free

JARVIS needs three things: (a) something that runs on a schedule,
(b) memory that survives, (c) the ability to run its own Python against
its own data.

### Your Windows PC

- **Schedule:** Windows Task Scheduler, built into Windows. No account, no
  quota, no bill.
- **Memory:** the repo folder on your disk. It is a file on a hard drive.
  It survives a reboot the same way your documents do.
- **Local code and local data:** yes — and this is the only option on the
  list that can do it. It is also **the only thing that can reach MT5**.
- **Verified limits:** none to verify. It is part of the operating system
  you already paid for. I could not reach Microsoft's documentation to cite
  the Task Scheduler details, so treat the exact wake/sleep behaviour as
  unconfirmed until you see it in the app.

### GitHub Actions (scheduled workflows)

Every number below is from GitHub's own docs source.

- **Cost:** "GitHub Actions usage is **free** for **self-hosted runners**
  and for **public repositories** that use standard GitHub-hosted runners."
  Your repo is public, so **the minute quota does not apply to you.**
  (`content/billing/concepts/product-billing/github-actions.md`)
- For reference, if you ever make it private: Free plan gets **2,000
  minutes/month, 500 MB artifact storage, 10 GB cache storage per
  repository**. (`data/reusables/billing/actions-included-quotas.md`)
- **Job timeout:** **6 hours** per job on a GitHub-hosted runner. Job is
  killed at that point. (`content/actions/reference/limits.md`)
- **Whole workflow run limit:** **35 days**, then cancelled. (same file)
- **Concurrent jobs, Free plan:** **20**. (same file)
- **Shortest schedule:** **once every 5 minutes.** Times are in UTC.
  (`data/reusables/repositories/actions-scheduled-workflow-example.md`)
- **Scheduled runs only happen on the default branch** — for you that is
  `main`, *not* `claude/jarvis-ai-operating-system-2xaclm`.
  (`content/actions/reference/workflows-and-actions/events-that-trigger-workflows.md`)
- **In a public repository, scheduled workflows are automatically disabled
  when no repository activity has occurred in 60 days.** (same file)
- **Schedules are not punctual.** GitHub's own wording: the event "can be
  delayed during periods of high loads... If the load is sufficiently high
  enough, **some queued jobs may be dropped**." They advise not scheduling
  on the hour. (`data/reusables/actions/schedule-delay.md`)
- **Logs and artifacts are kept 90 days by default.**
  (`content/actions/how-tos/manage-workflow-runs/download-workflow-artifacts.md`)
- **Cache is not memory:** "GitHub will remove any cache entries that have
  not been accessed in over 7 days."
  (`content/actions/reference/workflows-and-actions/dependency-caching.md`)
- Useful safety detail: pushes made by the workflow's own built-in token
  "will not create a new workflow run" — so a job that commits its results
  cannot trigger itself in an endless loop.
  (`data/reusables/actions/actions-do-not-trigger-workflows.md`)

**Can it run local code against local data?** It can run the repo's Python
against data committed in the repo. It **cannot** see your PC, your disk,
or MT5. Ever.

### Cloudflare Workers free plan — discarded

- Free plan: **100,000 requests/day**, **128 MB memory**, **5 cron triggers
  per account**, and **CPU time of 10 ms**.
- Specifically: **"CPU time per Cron Trigger — Workers Free: 10 ms."**
  (`cloudflare/cloudflare-docs`, `src/content/docs/workers/platform/limits.mdx`)

Ten milliseconds. A single `autosearch.py` run takes about 40 seconds. This
is off by a factor of four thousand. It is not a candidate. Discarded.

### Oracle Cloud "Always Free" — a real free server, with a real catch

- Oracle's own words: **"Always Free services are available for an
  unlimited time."** It includes **"two compute instances"**, block storage
  and object storage. (`oracle.com/cloud/free`, and its FAQ)
- **The catch, verbatim from Oracle:** "Accounts left idle for 30 days or
  more may be deemed abandoned and become eligible for **suspension or
  termination**."
- **I could not verify the exact CPU/RAM/storage numbers.** Oracle's detail
  pages were blocked from here. Do not let me tell you it is "4 cores and
  24 GB" — I have not read that. Check it yourself before relying on it.
- It runs Linux. It cannot run MT5 and cannot see your PC.

### The ones I refuse to rate

PythonAnywhere, Render, Fly.io, Railway, Replit. All blocked from here.
Free-tier terms on these services change often and I will not repeat what I
half-remember. Unverified.

---

## 2. The simplest architecture using what you already have

You already own every piece. Nothing to sign up for.

```
   Your Windows PC (already running MT5)
   |
   |-- C:\signals\                  the repo, on your own disk
   |     JARVIS/state/*.md          <-- the memory. Plain text files.
   |     JARVIS/research/*.py       <-- the work. Pure Python, no installs.
   |     data/                      <-- the candles
   |
   |-- Task Scheduler                runs one .bat file on a timer
   |
   `-- git push  ------------------->  github.com/veer7710/signals
                                       the offsite copy
```

**Where state lives:** in files in `C:\signals\JARVIS\state\`. That is it.
There is no database and no server.

**How it survives a reboot:** the same way any file on your C: drive
survives a reboot — it is written to disk, not held in memory. When the PC
comes back on, Task Scheduler starts again on its own and the files are
exactly where they were.

**How it survives the PC dying:** every run ends with `git push`. GitHub
then holds a second copy of every state file and every result. If the
laptop is stolen tomorrow, you `git clone` onto a new machine and JARVIS
remembers everything up to the last push.

**Size is not a concern.** GitHub recommends repositories stay "ideally
less than 1 GB, and less than 5 GB is strongly recommended"; individual
files warn at 50 MiB and are blocked at 100 MiB
(`content/repositories/working-with-files/managing-large-files/about-large-files-on-github.md`).
Your whole repo is currently about 2.6 MB. You have room for years of this.

---

## 3. The honest catch with each option

**Your PC.** *The machine has to be on.* If it is asleep, shut down, or the
lid is closed, nothing runs and nothing is missed gracefully — it simply
does not happen. This is the entire downside, and it is a real one. Task
Scheduler has a "run as soon as possible after a missed start" setting that
softens it; I could not reach Microsoft's docs to confirm the wording, so
look for it yourself in the app.

**GitHub Actions.** Four separate traps:
1. It runs on `main` only. JARVIS currently lives on a different branch. A
   scheduled workflow on that branch will never fire.
2. Public repo means **the whole world can read it**. That is fine for
   backtest code and awful for anything resembling a broker credential.
   The existing "no secrets in the repo" rule is doing real work here.
3. **It stops itself after 60 days of no repo activity** on a public repo.
   Quietly. You get an email; if you ignore it, JARVIS silently dies.
4. It cannot see MT5 or your disk, so it can never do the one job only your
   PC can do.
5. Jobs are killed at 6 hours, and scheduled jobs can be late or dropped
   entirely under load.

**Cloudflare Workers.** 10 ms of CPU. Not a catch, a wall.

**Oracle Always Free.** Free forever *as long as the account is not idle*
for 30 days — and an abandoned account is "eligible for suspension or
termination", which means the server and everything on it can be taken
away. A free VM you must remember to log into is a chore with a deadline
attached. It also still cannot touch MT5.

**Anything with a "free tier" I could not verify.** The general pattern
worth being cynical about: free tiers that sleep after inactivity, wipe
their disk on every redeploy, and change terms without notice. Do not put
JARVIS's only copy of its memory on one.

---

## 4. Recommendation: your own PC, plus GitHub as the backup copy

One recommendation, and it is the boring one. **Run JARVIS on the Windows
PC that is already running MT5, and push to GitHub after every run.**

Why: it is the only option that can reach MT5, it has no quota to run out
of, no free tier that can be withdrawn, and its memory is just files on
your own disk. GitHub is not the runner — it is the second copy.

### Step by step

You have never used Task Scheduler. That is fine; it is a normal Windows
app with buttons.

**Step 1 — check the repo is on your PC.**
Open the folder `C:\signals`. If it is not there, open Command Prompt
(press the Windows key, type `cmd`, press Enter) and type:

```
cd C:\
git clone https://github.com/veer7710/signals
```

**Step 2 — make the file that does the work.**
Open Notepad. Paste this in exactly:

```
cd /d C:\signals
git pull
python JARVIS\research\test_engine.py
python JARVIS\research\autosearch.py --fast
git add -A
git commit -m "nightly run"
git push
```

Save it as `C:\signals\run_jarvis.bat`. In Notepad's save box, change
"Save as type" to **All Files** first, or Windows will name it
`run_jarvis.bat.txt` and it will not work.

**Step 3 — test it by hand before automating it.**
Double-click `run_jarvis.bat`. A black window opens and text scrolls past.
You want to see `ALL TESTS PASSED` go by. If you see an error instead,
stop here and tell me what it says. Never automate something you have not
watched work once.

**Step 4 — open Task Scheduler.**
Press the Windows key, type `Task Scheduler`, press Enter.

**Step 5 — create the task.**
On the right-hand side click **Create Basic Task...**
- Name: `JARVIS nightly`. Click Next.
- Choose **Daily**. Click Next.
- Pick a time the PC is on and you are not using it. **Avoid times on the
  hour.** 11:17 pm is a better choice than 11:00 pm. Click Next.
- Choose **Start a program**. Click Next.
- Click **Browse**, find `C:\signals\run_jarvis.bat`, select it.
- Click Next, then Finish.

**Step 6 — make it catch up after the PC was off.**
In the middle list, find `JARVIS nightly`, right-click it, choose
**Properties**, go to the **Settings** tab, and tick **"Run task as soon as
possible after a scheduled start is missed."** Click OK. Now a night with
the PC switched off is recovered the next morning instead of lost.

**Step 7 — prove it works without waiting a day.**
Right-click `JARVIS nightly` and choose **Run**. The black window should
appear and do the same thing it did in Step 3. Then check
`https://github.com/veer7710/signals` in a browser — you should see a fresh
"nightly run" commit. That commit is the proof that your memory made it
off the machine.

### What this does not do

It does not run when the PC is off. There is no free way around that other
than leaving a machine on, and a machine you own that is already on is the
cheapest such machine. Do not buy anything to fix this.

### If you later want a second layer

A scheduled GitHub Actions workflow on `main` can act as a watchdog — it
costs nothing on a public repo, and it can check whether the PC has pushed
recently and open an issue if it has not. That is a separate small job,
worth doing only after the local one has run reliably for a few weeks.
Remember it needs to live on `main`, and that repo activity every 60 days
is what keeps it alive.
