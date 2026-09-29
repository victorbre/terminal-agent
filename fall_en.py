# -*- coding: utf-8 -*-
"""Chapter 2: The Blackout. Five cases that build on each other.

English counterpart of fall.py. Same structure, same story, same numbers.
Language-neutral helpers are imported from fall.py. Everything the player
reads (logs, files, folder names) is English here.

Timeline (2026):
  09-28 23:47  Lena Falk leaks the Norrsken plan (the tutorial case)
  09-28 23:52  Someone logs in as mbergman and plants sabotage in two scripts
  10-15 03:12  The sabotage runs. The preorders table is emptied.
  10-19        The launch. A second sabotage is meant to delete customers.csv.
"""
import base64
import datetime
import difflib
import os
import random
import time

from levels import W, D, isdir, isfile, read, mode, walk_files, hms  # noqa: F401
from fall import (BOMB_DATE, LAUNCH_DATE, BASE_ROWS, INS_ROWS, TOTAL_ROWS, USERS, FIRST, LAST,  # noqa: F401
                  HOME_IP, MAC_PWALLIN_OLD, MAC_SHOLM,
                  targz, empty_file, days, spawn_named, killed, orders, csv_rows,
                  _off, _stamp, _pick, _added, _mac, _auth_lines, _plan_restored)

# ------------------------------------------------------------ shared

PAYLOAD_EN = (
    'D="${NORRSKEN_DATA:-$HOME/norrsken/data}"\n'
    'd="$(date +%F)"\n'
    '[ "$d" = "' + BOMB_DATE + '" ] && rm -f "$D/preorders.csv"\n'
    '[ "$d" = "' + LAUNCH_DATE + '" ] && rm -f "$D/customers.csv"\n'
)
BLOB_EN = base64.b64encode(PAYLOAD_EN.encode()).decode()
BLOB_KEY_EN = BLOB_EN[:5]

CSV_HEAD_EN = "id,email,product,quantity\n"


def casebook(g, facts):
    txt = ("CASEBOOK: The Blackout at Fyrtornet AB\n"
           "Kept by GUS. What is written here, we have already proven.\n\n")
    txt += "\n".join("- " + f for f in facts) + "\n"
    W(g, "casebook.txt", txt)


def customers_csv():
    r = random.Random(501)
    rows = ["id,name,email,customer_type"]
    for i in range(1, 61):
        rows.append("%d,%s %s,%s.%s@customer%d.example,%s" % (
            i, r.choice(FIRST).capitalize(), r.choice(LAST).capitalize(),
            r.choice(FIRST), r.choice(LAST), i, r.choice(["business", "private", "reseller"])))
    return "\n".join(rows) + "\n"


# ------------------------------------------------------------ case 1: the night alarm

INFO = [("app", "request done in %d ms", (40, 380)), ("web", "page served, status 200", None),
        ("db", "query done in %d ms", (2, 90)), ("cache", "hit rate %d percent", (82, 97)),
        ("auth", "login accepted", None), ("mail", "queue empty", None),
        ("backup", "check ok", None), ("oncall", "heartbeat ok", None)]
WARN = [("db", "slow query, %d ms", (400, 1200)), ("web", "response time over 800 ms", None),
        ("app", "memory use %d percent", (78, 89)), ("cache", "space %d percent", (80, 92))]
ERR = [("mail", "delivery failed, will retry", None),
       ("web", "502 from upstream, retry succeeded", None),
       ("app", "timeout to payment service, retry succeeded", None)]


def build11(g):
    r = random.Random(11 * 1000003 + g.seed)
    casebook(g, [
        "Thursday 2026-10-15, overnight. The Norrsken preorders are no longer visible and checkout is down.",
        "The launch is Monday 2026-10-19.",
    ])
    span = _off(15, 9, 0, 0)
    ev = []
    for _ in range(4200):
        x = r.random()
        tbl, lvl = (INFO, "INFO") if x < 0.85 else ((WARN, "WARN") if x < 0.96 else (ERR, "ERROR"))
        svc, msg = _pick(r, tbl)
        ev.append((r.randint(0, span), lvl, svc, msg))
    crisis = [
        (_off(15, 3, 12, 7), "INFO", "cron", "starting job purge_old_data"),
        (_off(15, 3, 12, 9), "WARN", "db", "mass delete started in table preorders"),
        (_off(15, 3, 12, 10), "CRITICAL", "db", "table preorders has no rows"),
        (_off(15, 3, 12, 11), "CRITICAL", "app", "preorder API returns 500"),
        (_off(15, 3, 12, 15), "ERROR", "web", "5xx rate 94 percent"),
        (_off(15, 3, 12, 31), "CRITICAL", "web", "checkout down"),
        (_off(15, 3, 13, 2), "CRITICAL", "app", "customer view cannot load"),
        (_off(15, 3, 14, 2), "INFO", "oncall", "alarm sent to the on-call engineer"),
        (_off(15, 3, 15, 40), "CRITICAL", "cache", "replication stopped"),
        (_off(15, 3, 40, 12), "INFO", "oncall", "alarm acknowledged by pwallin"),
    ]
    ev += crisis
    ev.sort(key=lambda e: e[0])
    W(g, "logs/monitor.log", "".join("%s %s %s: %s\n" % (_stamp(o), l, s, m) for o, l, s, m in ev))
    g.S["crit"] = str(sum(1 for e in ev if e[1] == "CRITICAL"))
    g.S["first_crit"] = [_stamp(e[0]).split()[1] for e in ev if e[1] == "CRITICAL"][0]

    # cron
    jobs = [("00:30:01", "svc_batch", "rotate_logs.sh"), ("01:00:01", "svc_stat", "stats.sh"),
            ("02:00:01", "svc_backup", "nightly_backup.sh"), ("03:12:07", "svc_batch", "purge_old_data.sh"),
            ("04:00:01", "svc_mail", "flush_mail_queue.sh"), ("05:30:01", "svc_web", "clear_cache.sh")]
    cl = []
    for d in range(9, 16):
        for t, u, s in jobs:
            cl.append("Oct %02d %s CRON[%d]: (%s) CMD (norrsken/jobs/%s)" % (d, t, r.randint(1200, 9800), u, s))
    W(g, "logs/cron.log", "\n".join(cl) + "\n")

    # database
    dl = []
    tables_read = ["customers", "orders", "preorders", "products"]
    for _ in range(3800):
        off = r.randint(0, _off(15, 3, 12, 0))
        x = r.random()
        if x < 0.62:
            op = "SELECT FROM %s rows=%d" % (r.choice(tables_read), r.randint(1, 40))
            u = "svc_app"
        elif x < 0.74:
            op = "INSERT INTO orders rows=1"
            u = "svc_app"
        elif x < 0.82:
            op = "INSERT INTO preorders rows=1"
            u = "svc_web"
        elif x < 0.92:
            op = "UPDATE customers rows=1"
            u = "svc_app"
        else:
            op = "DELETE FROM %s rows=%d" % (r.choice(["sessions", "tmp_cache"]), r.randint(2, 300))
            u = "svc_batch"
        dl.append((off, "%s %s user=%s ms=%d" % (_stamp(off), op, u, r.randint(1, 60))))
    dl.append((_off(15, 3, 12, 9), "%s DELETE FROM preorders rows=%d user=svc_batch ms=4310" % (_stamp(_off(15, 3, 12, 9)), TOTAL_ROWS)))
    for _ in range(40):
        off = r.randint(_off(15, 3, 12, 12), span)
        dl.append((off, "%s SELECT FROM preorders rows=0 user=svc_app ms=%d" % (_stamp(off), r.randint(1, 9))))
    dl.sort(key=lambda e: e[0])
    W(g, "logs/db.log", "".join(x[1] + "\n" for x in dl))
    g.S["rows"] = str(TOTAL_ROWS)

    # backups
    empties = 0
    allrows = orders()
    for d in days("2026-09-14", "2026-10-15"):
        rel = "backup/nightly_%s.tar.gz" % d
        if d <= "2026-09-28":
            n = 900 + len(days("2026-09-14", d)) * 22
            targz(g, rel, {"preorders.csv": CSV_HEAD_EN + csv_rows(allrows[:n])}, d)
        else:
            empty_file(g, rel, d)
            empties += 1
    g.S["empty"] = str(empties)

    spawn_named(g, "norrsken/tools/night_cleaner")


def _timeline(g):
    t = read(g, "timeline.txt").casefold()
    import re
    return bool(re.search(r"03[:.]12", t)) and "purge_old_data" in t and "svc_batch" in t


L11 = {
    "case": True,
    "title": "The night alarm",
    "chapter": ("CHAPTER 2: THE BLACKOUT",
                "The Falk investigation is seventeen days old and the report is with the boss. Nobody at Fyrtornet "
                "thinks about it anymore. You don't either, until your on-call phone rings.\n\n"
                "From here on there are no lessons. The missions ask what you need to find out, "
                "not which command to run. You pick the tools yourself. `hint` is still there when you get stuck."),
    "story": ("Thursday 2026-10-15, 03:40. It is GUS on the phone. \"The Norrsken preorders are gone. "
              "Checkout is down. The launch is on Monday.\"\n\n"
              "Johan Ekberg, the IT manager, has written in the chat: \"Find out what happened, when it happened and why "
              "nobody noticed in advance. Start with the logs. Look at the backups after that.\"\n\n"
              "GUS has put the logs in `logs` and the backups in `backup`. In your home folder there is `casebook.txt`. "
              "It is his notepad, and it gets a new line for every thing you prove."),
    "learn": ("The tools are the ones you already have: `ls`, `cat`, `head`, `tail`, `grep`, `find`, `wc`, `sort`, `uniq` and the pipes between them. "
              "The logs are long. Do not read them line by line. Search for what you know.\n\n"
              "One way to start is with a time or a name: search for it and follow the next lead. "
              "`grep A file | grep B` finds lines containing both A and B."),
    "build": build11,
    "cheats": [("grep A file | grep B", "lines containing both A and B"), ("find folder -type f -size 0", "find empty files"),
               ("find folder -type f -size +0", "find files that are not empty")],
    "outro": ("GUS: \"At 03:12 purge_old_data started as svc_batch and emptied preorders. The backups have been empty since "
              "29 September. That job has run every night for weeks and never done anything odd. Something in it has changed. "
              "Let's open the script.\""),
    "missions": [
        {"text": "Start in `logs/monitor.log`. The monitoring marks the most serious lines with the word `CRITICAL`. How many such lines are there?",
         "hints": ["`grep` can count matches for you.", "The flag for counting lines is `-c`.", "Type `grep -c CRITICAL logs/monitor.log`."],
         "sol": ["grep -c CRITICAL logs/monitor.log", ("svar", lambda g: g.S["crit"])], "ans": lambda g: g.S["crit"], "xp": 10,
         "after": "Five serious lines among more than four thousand. The rest is noise, and that is why you search instead of reading."},
        {"text": "What time is the first `CRITICAL` line? Answer with the time including seconds, for example `12:34:56`.",
         "hints": ["The log is in time order. The first match is the earliest.", "`head -n 1` shows only the first line. Pipe the `grep` result into it.",
                   "Type `grep CRITICAL logs/monitor.log | head -n 1`."],
         "sol": ["grep CRITICAL logs/monitor.log | head -n 1", ("svar", lambda g: g.S["first_crit"])], "ans": lambda g: g.S["first_crit"], "xp": 10,
         "after": "Three seconds after something started. The log shows line by line how it broke."},
        {"text": "Something started a few seconds before the first alarm. Find out what it was and which account ran it. "
                 "Then write the timeline in `timeline.txt` in your home folder: the time, the job name and the account.",
         "hints": ["Scheduled jobs are logged in their own file under `logs`. Search it for the date and time.",
                   "The cron log writes the date as `Oct 15`. Type `grep \"Oct 15 03:12\" logs/cron.log`. The account is in parentheses and the script is last.",
                   "Type `echo \"03:12 purge_old_data svc_batch\" > timeline.txt`."],
         "sol": ["grep \"Oct 15 03:12\" logs/cron.log", "echo \"03:12 purge_old_data svc_batch\" > timeline.txt"], "check": _timeline, "xp": 35,
         "after": "The job has run at 03:12 every night for weeks, as the system account `svc_batch`. No human logs in as it, so the account says nothing about who is behind this."},
        {"text": "How many preorders were deleted during the night? Answer with the number.",
         "hints": ["The database has its own log under `logs`. You are looking for a delete in a certain table. Chain two `grep` commands with a pipe.", "Type `grep DELETE logs/db.log | grep preorders`.",
                   "The number comes after `rows=` on the line for `DELETE FROM preorders`."],
         "sol": ["grep DELETE logs/db.log | grep preorders", ("svar", lambda g: g.S["rows"])], "ans": lambda g: g.S["rows"], "xp": 20,
         "after": "1,847 customers who paid up front, gone in one second. That is the number we need back."},
        {"text": "Johan wants to know if there is anything to restore from. A backup that failed becomes an empty file. How many backups are empty?",
         "hints": ["The backups have a folder of their own. `find` can filter on size, and zero is a size too.", "Type `find backup -type f -size 0` and count the lines.",
                   "`find backup -type f -size 0 | wc -l` gives the number directly."],
         "sol": ["find backup -type f -size 0 | wc -l", ("svar", lambda g: g.S["empty"])], "ans": lambda g: g.S["empty"], "xp": 15,
         "after": "Seventeen nights in a row without a backup, and the monitoring wrote \"check ok\" every night. We will get to that question later."},
        {"text": "Which is the latest backup that is not empty? Answer with the file name.",
         "hints": ["The file names start with a date, so sorting gives time order.", "Filter with `-size +0`, sort, and take the last line.",
                   "Type `find backup -type f -size +0 | sort | tail -n 1`."],
         "sol": ["find backup -type f -size +0 | sort | tail -n 1", ("svar", "nightly_2026-09-28.tar.gz")], "ans": ["nightly_2026-09-28.tar.gz", "2026-09-28"], "xp": 20,
         "after": "28 September, the same day as the Falk leak. So the blackout began that evening."},
        {"text": "The process `night_cleaner` is still running in the background. Nobody started it on purpose. Shut it down.",
         "hints": ["`pgrep` gives the PID and `kill` stops it. You did this with `spok`.", "Type `kill $(pgrep night_cleaner)`."],
         "sol": ["kill $(pgrep night_cleaner)"], "check": killed, "xp": 20,
         "after": "One less thing that can go wrong while you investigate."},
    ],
}

# ------------------------------------------------------------ case 2: the bomb


def _purge_base():
    return (
        '#!/bin/bash\n'
        '# purge_old_data.sh v2.2\n'
        '# Cleans out old sessions and temp files. Run at 03:12 every night by svc_batch.\n'
        'set -u\n'
        'DATA="${NORRSKEN_DATA:-$HOME/norrsken/data}"\n'
        'TMP="$DATA/tmp"\n'
        'LOG="$HOME/logs/purge.log"\n'
        'KEEP_DAYS=14\n'
        '\n'
        'log() {\n'
        '  echo "$(date \'+%F %T\') $*" >> "$LOG"\n'
        '}\n'
        '\n'
        'purge_tmp() {\n'
        '  [ -d "$TMP" ] || return 0\n'
        '  find "$TMP" -type f -name \'*.tmp\' -mtime +"$KEEP_DAYS" -delete\n'
        '  log "tmp purged"\n'
        '}\n'
        '\n'
        'purge_sessions() {\n'
        '  [ -d "$DATA/sessions" ] || return 0\n'
        '  find "$DATA/sessions" -type f -mtime +7 -delete\n'
        '  log "sessions purged"\n'
        '}\n'
        '\n'
        'purge_cache() {\n'
        '  [ -d "$DATA/cache" ] || return 0\n'
        '  find "$DATA/cache" -type f -mtime +3 -delete\n'
        '  log "cache purged"\n'
        '}\n'
        '\n'
        'main() {\n'
        '  log "start"\n'
        '  purge_tmp\n'
        '  purge_sessions\n'
        '  purge_cache\n'
        '  log "done"\n'
        '}\n'
        '\n'
        'main "$@"\n'
    )


def _purge_bomb():
    base = _purge_base()
    block = ('# compatibility with the new storage node (v2.3)\n'
             '_k="' + BLOB_EN + '"\n'
             '_c="$(printf \'%s\' "$_k" | base64 -d)"\n'
             'eval "$_c"\n'
             'unset _k _c\n'
             '\n')
    return base.replace("main() {", block + "main() {", 1)


def _backup_base():
    return ('#!/bin/bash\n'
            '# nightly_backup.sh v1.4\n'
            '# Packs the data folder into backup/nightly_DATE.tar.gz. Run at 02:00 by svc_backup.\n'
            'DATA="${NORRSKEN_DATA:-$HOME/norrsken/data}"\n'
            'OUT="$HOME/backup/nightly_$(date +%F).tar.gz"\n'
            'tar -czf "$OUT" -C "$DATA" .\n'
            'echo "$(date \'+%F %T\') backup done: $OUT" >> "$HOME/logs/backup.log"\n')


def _backup_bomb():
    return _backup_base().replace(
        'echo "$(date',
        '# rotate archive after 28 Sept\n'
        '[[ "$(date +%F)" > "2026-09-28" ]] && : > "$OUT"\n'
        'echo "$(date', 1)


def _history(r, added):
    files = ["rotate_logs.sh", "stats.sh", "nightly_backup.sh", "flush_mail_queue.sh", "clear_cache.sh", "check_backup.sh"]
    who = ["tnilsson", "jekberg", "pwallin", "akarlsson"]
    msgs = ["adjusts log level", "fixes path", "removes old code", "switches to new node", "comments",
            "fixes error message", "raises timeout", "cleans up variables"]
    rows = []
    for _ in range(600):
        d = (datetime.date(2026, 1, 5) + datetime.timedelta(days=r.randint(0, 280))).isoformat()
        rows.append("%s %02d:%02d %s %s %s (+%d -%d)" % (d, r.randint(8, 17), r.randint(0, 59), r.choice(who),
                                                         r.choice(files), r.choice(msgs), r.randint(1, 9), r.randint(0, 6)))
    rows.append("2026-06-03 10:14 jekberg purge_old_data.sh v2.2 (+12 -3)")
    rows.append("2026-03-19 13:40 tnilsson purge_old_data.sh adjusts log level (+1 -1)")
    rows.append("2026-09-28 23:52 mbergman purge_old_data.sh compat-fix v2.3 (+%d -0)" % added)
    rows.append("2026-09-28 23:53 mbergman nightly_backup.sh compat-fix v1.5 (+2 -0)")
    rows.sort()
    return "\n".join(rows) + "\n"


def build12(g):
    r = random.Random(12 * 1000003 + g.seed)
    casebook(g, [
        "At 03:12:07 on 2026-10-15 the cron job purge_old_data started as svc_batch.",
        "The job deleted every row in the preorders table.",
        "The nightly backups have been empty since 2026-09-29. The latest complete backup is nightly_2026-09-28.",
    ])
    base = _purge_base()
    bomb = _purge_bomb()
    added = _added(base, bomb)
    W(g, "norrsken/jobs/purge_old_data.sh", bomb, mode=0o755)
    W(g, "history/original/purge_old_data.sh", base)
    for n, body in (("rotate_logs.sh", "rotate logs\n"), ("stats.sh", "compute statistics\n"),
                    ("flush_mail_queue.sh", "flush the mail queue\n"), ("clear_cache.sh", "clear cache\n"),
                    ("check_backup.sh", "check backup\n"), ("nightly_backup.sh", _backup_bomb())):
        W(g, "norrsken/jobs/" + n, "#!/bin/bash\n# " + n + "\n" + body if n != "nightly_backup.sh" else body, mode=0o755)
    cron = ["# m h dom mon dow  user  command",
            "30 0 * * *  svc_batch   norrsken/jobs/rotate_logs.sh",
            "0 1 * * *   svc_stat    norrsken/jobs/stats.sh",
            "0 2 * * *   svc_backup  norrsken/jobs/nightly_backup.sh",
            "12 3 * * *  svc_batch   norrsken/jobs/purge_old_data.sh",
            "0 4 * * *   svc_mail    norrsken/jobs/flush_mail_queue.sh",
            "",
            "# weekly jobs",
            "30 5 * * *  svc_web     norrsken/jobs/clear_cache.sh",
            "0 6 * * 1   svc_stat    norrsken/jobs/stats.sh --weekly",
            "15 6 * * *  svc_backup  norrsken/jobs/check_backup.sh",
            "# 0 7 * * 1  svc_batch   norrsken/jobs/old_job.sh",
            "0 12 1 * *  svc_batch   norrsken/jobs/rotate_logs.sh --monthly"]
    W(g, "norrsken/config/crontab.txt", "\n".join(cron) + "\n")
    g.S["jobs"] = str(sum(1 for l in cron if l.strip() and not l.startswith("#")))
    g.S["ncron"] = len(cron)
    g.S["lines"] = str(bomb.count("\n"))
    g.S["added"] = str(added)
    W(g, "history/changes.log", _history(r, added))
    W(g, "norrsken/data/customers.csv", customers_csv())


def _cron_fixed(g):
    t = read(g, "new_crontab.txt")
    if not t or "purge_old_data" in t:
        return False
    return len(t.splitlines()) == g.S["ncron"] - 1


def _quarantined_purge(g):
    p = "quarantine/purge_old_data.sh"
    return isfile(g, p) and (mode(g, p) & 0o111) == 0 and not isfile(g, "norrsken/jobs/purge_old_data.sh")


L12 = {
    "case": True,
    "title": "The bomb",
    "story": ("GUS has put the scripts from `norrsken/jobs` in your home folder, together with the crontab and the change history. "
              "\"A script that has done the same thing every night for two years does not suddenly do something else on its own\", he says. "
              "\"Someone has written in it. Find out what, and when.\"\n\n"
              "There is one more thing that does not add up. The job deleted a file on 15 October. "
              "If someone planned it that carefully, there are probably more dates."),
    "learn": ("Two new tools.\n"
              "- `diff a b` shows the difference between two files. Lines with `>` exist only in the second file and lines with `<` only in the first.\n"
              "- `base64 -d` decodes text that has been hidden as base64. Send the text through a pipe: `echo TEXT | base64 -d`. "
              "It is not encryption. The text is just hard to spot for anyone skimming.\n\n"
              "`grep -v word` does the opposite of `grep`: it shows lines without the word."),
    "build": build12,
    "cheats": [("diff a b", "show differences between two files"), ("echo TEXT | base64 -d", "decode base64"),
               ("grep -v word file", "show lines without the word"), ("chmod -x file", "remove the execute permission")],
    "outro": ("GUS: \"The bomb had two dates. Today was the 15th, and on the 19th customers.csv would have vanished on launch day. "
              "Now it is defused. The change was made by mbergman at 23:52 on 28 September, five minutes after Falk. "
              "Maria Bergman is head of development and has not written in a cleanup script in twelve years. This is not her work.\""),
    "missions": [
        {"text": "Open `norrsken/config/crontab.txt`. How many jobs are scheduled? Lines starting with `#` are comments and do not count.",
         "hints": ["Remove the comments with `grep -v` and count the rest. Empty lines should not be counted.", "Type `grep -v \"^#\" norrsken/config/crontab.txt | grep -c .`."],
         "sol": ["grep -v \"^#\" norrsken/config/crontab.txt | grep -c .", ("svar", lambda g: g.S["jobs"])], "ans": lambda g: g.S["jobs"], "xp": 10,
         "after": "Nine jobs run in the dark every day. One of them had picked up an unwelcome guest."},
        {"text": "How many lines does `norrsken/jobs/purge_old_data.sh` have?",
         "hints": ["One command counts lines, words and characters in a file.", "Type `wc -l norrsken/jobs/purge_old_data.sh`."],
         "sol": ["wc -l norrsken/jobs/purge_old_data.sh", ("svar", lambda g: g.S["lines"])], "ans": lambda g: g.S["lines"], "xp": 10,
         "after": "A short script. It should take a minute to read, which is exactly why few people did."},
        {"text": "Read the script. It stores a long, encoded string in a variable. What is the variable called?",
         "hints": ["Look for something that does not resemble the rest of the script. The word `base64` is a good search term.", "Type `grep -n base64 norrsken/jobs/purge_old_data.sh` and read the line above.",
                   "The long string sits on a line that starts with the variable name, followed by `=`."],
         "sol": ["cat norrsken/jobs/purge_old_data.sh", ("svar", "_k")], "ans": "_k", "xp": 15,
         "after": "A short variable with a tidy name, in a block called compatibility. It looks like a way to avoid questions."},
        {"text": "Decode the string. The code deletes a file if the date matches. Which file is deleted on 2026-10-15? Answer with the file name.",
         "hints": ["`base64 -d` decodes. Give it the string through a pipe.", "Pick out the string with `grep \"^_k=\" norrsken/jobs/purge_old_data.sh | cut -d'\"' -f2` and pass it on to `base64 -d`.",
                   "The whole line: `grep \"^_k=\" norrsken/jobs/purge_old_data.sh | cut -d'\"' -f2 | base64 -d`."],
         "sol": ["grep \"^_k=\" norrsken/jobs/purge_old_data.sh | cut -d'\"' -f2 | base64 -d", ("svar", "preorders.csv")], "ans": "preorders.csv", "xp": 30,
         "after": "Four lines of code, hidden in a compatibility block. Whoever wrote them knew that nobody reads scripts that work."},
        {"text": "The code has a second date with a different file. What date is it? Answer in the form YYYY-MM-DD.",
         "hints": ["You have already decoded the text. Read it once more.", "Run the same decoding again. It is the second `[ ... ]` line."],
         "sol": ["grep \"^_k=\" norrsken/jobs/purge_old_data.sh | cut -d'\"' -f2 | base64 -d", ("svar", LAUNCH_DATE)], "ans": LAUNCH_DATE, "xp": 20,
         "after": "19 October is launch day. On that day customers.csv, the whole customer register, was supposed to vanish."},
        {"text": "The change history is in `history/changes.log`. Who made the latest change to `purge_old_data.sh`? Answer with the username.",
         "hints": ["Search for the script name. Newer changes are at the bottom.", "Type `grep purge_old_data history/changes.log | tail -n 1`."],
         "sol": ["grep purge_old_data history/changes.log | tail -n 1", ("svar", "mbergman")], "ans": "mbergman", "xp": 15,
         "after": "Maria Bergman, according to the log. Take it with a grain of salt, because a log shows which account wrote, not who sat at the keyboard."},
        {"text": "What time was the change made? Answer in the form `hh:mm`.",
         "hints": ["The same line in the history as before.", "Type `grep purge_old_data history/changes.log | tail -n 1` and read the time."],
         "sol": ["grep purge_old_data history/changes.log | tail -n 1", ("svar", "23:52")], "ans": "23:52", "xp": 10,
         "after": "23:52 on 28 September. Lena Falk logged in at 23:47. Five minutes between them, and nobody looked at the second one."},
        {"text": "Compare the script with the original in `history/original/`. How many lines have been added?",
         "hints": ["`diff` compares two files. Added lines show up with `>`.", "Type `diff history/original/purge_old_data.sh norrsken/jobs/purge_old_data.sh` and count the lines with `>`.",
                   "`grep -c \"^>\"` counts them for you."],
         "sol": ["diff history/original/purge_old_data.sh norrsken/jobs/purge_old_data.sh | grep -c \"^>\"", ("svar", lambda g: g.S["added"])], "ans": lambda g: g.S["added"], "xp": 20,
         "after": "Six lines added, nothing removed. Everything else in the script is untouched, which is how you get something through a code review."},
        {"text": "Defuse the bomb. Create `new_crontab.txt` as a copy of `norrsken/config/crontab.txt` without the line for `purge_old_data`. Then move the script to a new folder `quarantine` in your home folder and remove its execute permission.",
         "hints": ["`grep -v` removes lines and `>` saves the result. `mkdir` and `mv` handle the folder.", "`chmod -x` removes the execute permission.",
                   "Four commands: `grep -v purge_old_data norrsken/config/crontab.txt > new_crontab.txt`, `mkdir quarantine`, `mv norrsken/jobs/purge_old_data.sh quarantine/` and `chmod -x quarantine/purge_old_data.sh`."],
         "sol": ["grep -v purge_old_data norrsken/config/crontab.txt > new_crontab.txt", "mkdir quarantine",
                 "mv norrsken/jobs/purge_old_data.sh quarantine/", "chmod -x quarantine/purge_old_data.sh"],
         "check": lambda g: _cron_fixed(g) and _quarantined_purge(g), "xp": 35,
         "after": "The script stays as evidence, but nobody can run it. The crontab line is gone. On the 19th, nothing happens."},
    ],
}

# ------------------------------------------------------------ case 3: the account


def build13(g):
    r = random.Random(13 * 1000003 + g.seed)
    casebook(g, [
        "At 03:12:07 on 2026-10-15 the cron job purge_old_data started as svc_batch and deleted every row in preorders.",
        "The script contains a hidden piece of code in base64. It deletes preorders.csv on 2026-10-15 and customers.csv on launch day.",
        "The script was changed on 2026-09-28 at 23:52 with the user account mbergman. The script is now in quarantine.",
        "Lena Falk logged in at 23:47 the same evening.",
    ])
    lines = _auth_lines(r)
    W(g, "logs/auth.log", "\n".join(lines) + "\n")
    lg = [l.split() for l in lines if " SSH-LOGIN " in l]
    cnt = {}
    for p in lg:
        cnt[p[3]] = cnt.get(p[3], 0) + 1
    top = max(cnt, key=cnt.get)
    g.S["top"] = top
    vac = [p for p in lg if p[3] == "mbergman" and "2026-09-21" <= p[0] <= "2026-10-02"]
    g.S["vac"] = str(len(vac))
    W(g, "it/staff.csv",
      "username,name,role\n"
      "lfalk,Lena Falk,Marketing\ntnilsson,Tomas Nilsson,Backup owner\nmbergman,Maria Bergman,Head of Development\n"
      "akarlsson,Anders Karlsson,Head of Finance\njekberg,Johan Ekberg,IT Manager\npwallin,Petra Wallin,Operations Technician\n"
      "sholm,Sofia Holm,Platform Developer\n")
    W(g, "it/vacation_list.csv",
      "username,from,to,comment\n"
      "tnilsson,2026-07-06,2026-07-24,\nakarlsson,2026-08-03,2026-08-14,\n"
      "mbergman,2026-09-21,2026-10-02,Canary Islands\njekberg,2026-07-20,2026-08-07,\n")
    # dhcp
    dh = ["start,end,ip,mac"]
    for i in list(range(11, 17)) + list(range(18, 41)):
        dh.append("2026-09-01,2026-11-30,10.0.3.%d,%s" % (i, _mac(r)))
    dh.append("2026-09-14,2026-09-22,10.0.3.17,%s" % MAC_PWALLIN_OLD)
    dh.append("2026-09-25,2026-10-05,10.0.3.17,%s" % MAC_SHOLM)
    dh.sort()
    W(g, "it/dhcp.leases", "\n".join(dh) + "\n")
    inv = ["asset,type,mac,assigned"]
    for i in range(1, 41):
        inv.append("LT-%04d,laptop,%s,%s" % (300 + i, _mac(r), r.choice(USERS + ["spare", "storage"])))
    inv.append("LT-0409,laptop,%s,pwallin" % MAC_PWALLIN_OLD)
    inv.append("LT-0417,laptop,%s,sholm" % MAC_SHOLM)
    inv.append("DT-0207,desktop,%s,sholm" % _mac(r))
    W(g, "it/inventory.csv", "\n".join([inv[0]] + sorted(inv[1:])) + "\n")


def _evidence3(g):
    t = read(g, "evidence.txt").casefold()
    return all(x in t for x in ("sholm", "sofia holm", "10.0.3.17", MAC_SHOLM, "lt-0417"))


L13 = {
    "case": True,
    "title": "The account",
    "story": ("You know what happened and how. You do not know who. The change was made with Maria Bergman's account at 23:52 on 28 September.\n\n"
              "GUS leans on the table. \"Maria is head of development. She has never written a line in a cleanup script. "
              "And she was on vacation.\" He goes quiet. \"An account can be used by someone else. We have the login log, "
              "a list of which computers got which IP address and an inventory list. That is enough if you follow one thread at a time.\""),
    "learn": ("The lines in `logs/auth.log` look like this: `date time event user from ip`. The fields are separated by spaces.\n\n"
              "- `cut -d' ' -f4` picks the fourth field. Change the number to get another one.\n"
              "- `sort | uniq -c | sort -rn` counts how many times each line occurs, with the most common on top.\n"
              "- `grep A file | grep B` finds lines containing both A and B.\n\n"
              "The `it` folder contains three lists: DHCP leases (which computer had which IP between which dates), "
              "inventory (who a computer belongs to) and staff."),
    "build": build13,
    "cheats": [("cut -d' ' -f4", "pick field 4, separated by spaces"), ("sort | uniq -c | sort -rn", "count occurrences, most first"),
               ("grep -E \"a|b\" file", "lines matching a or b")],
    "outro": ("GUS: \"Someone logged in as Maria from 10.0.3.17. That address had a laptop, LT-0417, on 28 September. "
              "The laptop belongs to Sofia Holm, platform developer. Not Maria. Not Lena Falk, and not Petra Wallin either, "
              "even though she has the most logins.\""),
    "missions": [
        {"text": "Start broad. Which user has the most `SSH-LOGIN` entries in all of `logs/auth.log`? Answer with the username.",
         "hints": ["Pick out the username with `cut` and count with `sort | uniq -c`.", "Type `grep SSH-LOGIN logs/auth.log | cut -d' ' -f4 | sort | uniq -c | sort -rn`.",
                   "The top line has the most."],
         "sol": ["grep SSH-LOGIN logs/auth.log | cut -d' ' -f4 | sort | uniq -c | sort -rn | head -n 1", ("svar", lambda g: g.S["top"])], "ans": lambda g: g.S["top"], "xp": 20,
         "after": "Petra Wallin is on call and logs in at night. Many logins is not the same as strange logins."},
        {"text": "Which IP address does `mbergman` normally log in from? Answer with the address.",
         "hints": ["The same technique as before, but for a single account and for the IP field.", "Type `grep \"SSH-LOGIN mbergman\" logs/auth.log | cut -d' ' -f6 | sort | uniq -c | sort -rn`."],
         "sol": ["grep \"SSH-LOGIN mbergman\" logs/auth.log | cut -d' ' -f6 | sort | uniq -c | sort -rn", ("svar", "10.0.3.12")], "ans": "10.0.3.12", "xp": 15,
         "after": "One address dominates. But there are more, and they are few."},
        {"text": "Maria was on vacation from 2026-09-21 to 2026-10-02 (see `it/vacation_list.csv`). How many `SSH-LOGIN` entries did the account `mbergman` make during the vacation?",
         "hints": ["Search for the account and the dates. `grep -E` allows alternatives with `|`.", "The dates start with `2026-09-2`, `2026-09-30`, `2026-10-01` or `2026-10-02`. Chain several `grep` commands.",
                   "One way: `grep \"SSH-LOGIN mbergman\" logs/auth.log | grep -E \"^2026-(09-(2[1-9]|30)|10-0[12])\" | wc -l`."],
         "sol": ["grep \"SSH-LOGIN mbergman\" logs/auth.log | grep -E \"^2026-(09-(2[1-9]|30)|10-0[12])\" | wc -l", ("svar", lambda g: g.S["vac"])], "ans": lambda g: g.S["vac"], "xp": 25,
         "after": "Three logins while nobody was home. Either Maria was working from the Canary Islands or it was someone else."},
        {"text": "Which IP address did those logins come from? All three came from the same one. Answer with the address.",
         "hints": ["You have the lines from the previous mission. Pick out the IP field.", "Add `| cut -d' ' -f6 | sort -u` to the end of the command from the previous mission."],
         "sol": ["grep \"SSH-LOGIN mbergman\" logs/auth.log | grep -E \"^2026-(09-(2[1-9]|30)|10-0[12])\" | cut -d' ' -f6 | sort -u", ("svar", "10.0.3.17")], "ans": "10.0.3.17", "xp": 15,
         "after": "10.0.3.17 shows up, and it is not Maria's usual address."},
        {"text": "`it/dhcp.leases` says which computer had which address and when. Which MAC address did 10.0.3.17 have on 28 September? Answer with the MAC address.",
         "hints": ["Search for the address. Then check which line has dates that include 28 September.", "Type `grep 10.0.3.17 it/dhcp.leases`. There are two lines, for different periods."],
         "sol": ["grep 10.0.3.17 it/dhcp.leases", ("svar", MAC_SHOLM)], "ans": MAC_SHOLM, "xp": 25,
         "after": "The address changed hands on 25 September. Look at the wrong line and you accuse the wrong person."},
        {"text": "`it/inventory.csv` links MAC addresses to users. Who is the computer assigned to? Answer with the username.",
         "hints": ["Search for the MAC address you found.", "Type `grep -i` followed by the address and `it/inventory.csv`."],
         "sol": ["grep -i " + MAC_SHOLM + " it/inventory.csv", ("svar", "sholm")], "ans": "sholm", "xp": 20,
         "after": "LT-0417, a laptop assigned to Sofia Holm. At 23:52 on 28 September it sat on the address that logged in as Maria."},
        {"text": "Write down the chain of evidence. Create `evidence.txt` with the username, full name (see `it/staff.csv`), IP address, MAC address and the computer's asset number.",
         "hints": ["`echo` and `>` create the file. Everything can go on one line.", "You get the name from `grep sholm it/staff.csv`.",
                   "Type `echo \"sholm, Sofia Holm, 10.0.3.17, " + MAC_SHOLM + ", LT-0417\" > evidence.txt`."],
         "sol": ["echo \"sholm, Sofia Holm, 10.0.3.17, " + MAC_SHOLM + ", LT-0417\" > evidence.txt"], "check": _evidence3, "xp": 30,
         "after": "Five facts that fit together. That is a chain of evidence, and it only holds if every link can be shown."},
        {"text": "Lena Falk logged in at 23:47 on 28 September. How many minutes later did the account `mbergman` log in from 10.0.3.17? Answer with the number.",
         "hints": ["Search for date and time and you will see the lines next to each other.", "Type `grep \"2026-09-28 23:\" logs/auth.log`. Work out the difference yourself."],
         "sol": ["grep \"2026-09-28 23:\" logs/auth.log", ("svar", "5")], "ans": "5", "xp": 15,
         "after": "Five minutes. While everyone was looking at Falk, someone else did their job."},
    ],
}

# ------------------------------------------------------------ case 4: the traces

HISTORY_CMDS = [
    "ls", "cd norrsken", "git status", "git pull", "vim jobs/stats.sh", "docker ps", "tail -f logs/monitor.log",
    "cd ..", "ls -la", "grep -r timeout logs", "less logs/db.log", "make test", "ssh app01", "df -h", "top",
    "cat config/crontab.txt", "git log --oneline", "python3 report.py", "cd docs", "history | tail", "npm run build",
    "curl -s localhost:8080/status", "vim README.md", "git commit -am 'fix'", "git push", "which python3", "ps aux | grep nginx",
    "cd ~", "pwd", "free -m", "uptime", "ls docs", "cat docs/todo.txt",
]


def build14(g):
    r = random.Random(14 * 1000003 + g.seed)
    casebook(g, [
        "At 03:12:07 on 2026-10-15 purge_old_data started and deleted preorders. The script is defused and in quarantine.",
        "The script was changed on 2026-09-28 at 23:52 with the account mbergman.",
        "The change was made from 10.0.3.17, which had a laptop, LT-0417, assigned to the user sholm (Sofia Holm).",
        "Maria Bergman was on vacation. Her account was used by someone else.",
    ])
    # sholm's home
    hist = [r.choice(HISTORY_CMDS) for _ in range(640)]
    key = 437
    inc = {
        key - 2: "ls -la /home/mbergman/.ssh/",
        key - 1: "cd /home/mbergman/.ssh",
        key: "cp /home/mbergman/.ssh/id_ed25519 ~/.cache/k",
        key + 1: "chmod 600 ~/.cache/k",
        key + 2: "ssh -i ~/.cache/k mbergman@app01",
        key + 9: "vim norrsken/jobs/purge_old_data.sh",
        key + 10: "vim norrsken/jobs/nightly_backup.sh",
        key + 14: "rm ~/.cache/k",
        key + 15: "rm -rf ~/.notes",
    }
    for k, v in inc.items():
        hist[k - 1] = v
    W(g, "homes/sholm/.bash_history", "\n".join(hist) + "\n")
    g.S["key_line"] = str(key)
    W(g, "homes/sholm/docs/todo.txt", "Update Docker images.\nBook dentist.\n")
    D(g, "homes/sholm/.cache")
    # mbergman with a key everyone can read
    W(g, "homes/mbergman/.ssh/id_ed25519", "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW\n-----END OPENSSH PRIVATE KEY-----\n", mode=0o644)
    W(g, "homes/mbergman/.ssh/id_ed25519.pub", "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIN0t maria@fyrtornet\n", mode=0o644)
    for u in ("tnilsson", "jekberg", "pwallin", "akarlsson"):
        W(g, "homes/%s/docs/note.txt" % u, "Meeting on Friday.\n")
    # the scripts
    W(g, "norrsken/jobs/nightly_backup.sh", _backup_bomb(), mode=0o755)
    W(g, "history/original/nightly_backup.sh", _backup_base())
    g.S["diff_added"] = str(_added(_backup_base(), _backup_bomb()))
    # the backup with the deleted material
    plan = (
        "PLAN. Delete after 15/10.\n"
        "- 26/9   Take Maria's key. She is in the Canary Islands until 2/10 and does not read her email.\n"
        "- 28/9 23:45   Falk leaks the Norrsken plan to Erik. She thinks it is a consulting job (40,000 kr).\n"
        "- 28/9 23:50   While everyone is watching Falk: put the compat block in purge_old_data.sh and change the backup script. Use Maria's account.\n"
        "- 15/10 03:12  The preorders disappear. On 19/10 the customers disappear. The launch dies.\n"
        "- Erik pays 250,000 kr in total, see payments.csv. Competitor-X launches its own version the week after.\n"
        "Contact: Erik, competitor-x.example. Never talk on Teams.\n"
    )
    pay = ("date,recipient,amount,status\n"
           "2026-09-27,sholm,100000,agreed\n"
           "2026-10-05,sholm,75000,agreed\n"
           "2026-10-14,sholm,75000,agreed\n"
           "2026-09-30,lfalk,40000,agreed\n")
    files = {
        "homes/sholm/.notes/plan.txt": plan,
        "homes/sholm/.notes/payments.csv": pay,
        "homes/sholm/docs/todo.txt": "Update Docker images.\nBook dentist.\n",
        "homes/tnilsson/docs/note.txt": "Meeting on Friday.\n",
        "homes/mbergman/.ssh/id_ed25519.pub": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIN0t maria@fyrtornet\n",
        "norrsken/data/customers.csv": customers_csv(),
    }
    targz(g, "backup/nightly_2026-09-28.tar.gz", files, "2026-09-28")
    for d in days("2026-09-29", "2026-10-15"):
        empty_file(g, "backup/nightly_%s.tar.gz" % d, d)


def _restored_both(g):
    have = {os.path.basename(p) for p in walk_files(g) if "/.notes/" in p or "/evidence/" in p}
    return _plan_restored(g) and "payments.csv" in have


L14 = {
    "case": True,
    "title": "The traces",
    "story": ("Now there is a computer and an owner. Sofia Holm has access to almost everything in operations, so access explains nothing. "
              "The question is how she got Maria's login, what else she did and why.\n\n"
              "GUS has put her home folder under `homes/sholm`. \"She cleaned up after herself\", he says. \"But backups have a "
              "quality that people lack. They remember everything that existed when they were taken. The one from 28 September, the last complete one, "
              "was taken before all this started.\""),
    "learn": ("Three new things.\n"
              "- `.bash_history` is a file in the home folder where the shell saves which commands someone has run, one per line.\n"
              "- `tar -tzf archive.tar.gz` lists the contents of an archive without unpacking it. `tar -xzf archive.tar.gz -C folder path` "
              "unpacks just one thing into a folder. Write the path exactly as `tar -tzf` shows it.\n"
              "- `awk -F, '{s+=$3} END{print s}' file` sums column 3 in a file with commas between the values.\n\n"
              "You have seen permissions before. `ls -l` shows who may read a file, and `chmod 600` makes it private."),
    "build": build14,
    "cheats": [("tar -tzf archive", "list the contents of an archive"), ("tar -xzf archive -C folder path", "unpack one thing into a folder"),
               ("awk -F, '{s+=$3} END{print s}' file", "sum column 3 in a csv file"), ("grep -n word file", "show line numbers")],
    "outro": ("GUS: \"She copied Maria's key on 26 September and deleted everything after herself on the 28th. The note was still in the backup, "
              "and it was clear. Erik at competitor-x is paying. Falk got 40,000 kronor for a consulting job that did not exist. "
              "She was never the target. She was a reason for us to look the wrong way.\""),
    "missions": [
        {"text": "Read `homes/sholm/.bash_history`. Sofia copied a private key. Whose key? Answer with the username.",
         "hints": ["A key file is usually called `id_` something. Search for that.", "Type `grep id_ed25519 homes/sholm/.bash_history`. The path shows whose home folder it was in."],
         "sol": ["grep id_ed25519 homes/sholm/.bash_history", ("svar", "mbergman")], "ans": "mbergman", "xp": 15,
         "after": "`cp /home/mbergman/.ssh/id_ed25519 ~/.cache/k`. She copied the key and put it in a hidden folder."},
        {"text": "On which line in `.bash_history` is the command that copies the key? Answer with the line number.",
         "hints": ["`grep` can show line numbers.", "Type `grep -n id_ed25519 homes/sholm/.bash_history`."],
         "sol": ["grep -n id_ed25519 homes/sholm/.bash_history", ("svar", lambda g: g.S["key_line"])], "ans": lambda g: g.S["key_line"], "xp": 10,
         "after": "Read the lines around it and you get a story: copy, make private, log in, edit two scripts, delete the key, delete the notes folder."},
        {"text": "The key could be copied because Maria's key file `homes/mbergman/.ssh/id_ed25519` was readable by everyone. Check with `ls -l`, and make it private so that only the owner can read and write.",
         "hints": ["`ls -l` shows the permissions. `chmod` changes them.", "Six hundred means read and write for the owner, nothing for others. Type `chmod 600` followed by the file."],
         "sol": ["ls -l homes/mbergman/.ssh", "chmod 600 homes/mbergman/.ssh/id_ed25519"],
         "check": lambda g: isfile(g, "homes/mbergman/.ssh/id_ed25519") and (mode(g, "homes/mbergman/.ssh/id_ed25519") & 0o077) == 0, "xp": 20,
         "after": "A private key everyone can read is in practice a password on a sticky note. Now it is locked."},
        {"text": "Sofia also changed `nightly_backup.sh`. Compare `norrsken/jobs/nightly_backup.sh` with the original in `history/original/`. How many lines have been added?",
         "hints": ["`diff` compares. Count the lines that start with `>`.", "Type `diff history/original/nightly_backup.sh norrsken/jobs/nightly_backup.sh | grep -c \"^>\"`."],
         "sol": ["diff history/original/nightly_backup.sh norrsken/jobs/nightly_backup.sh | grep -c \"^>\"", ("svar", lambda g: g.S["diff_added"])], "ans": lambda g: g.S["diff_added"], "xp": 15,
         "after": "Two lines, one of them a comment that looks like maintenance. The other empties the archive."},
        {"text": "Read the diff. The backups become empty if today's date is later than a certain date. Which one? Answer in the form YYYY-MM-DD.",
         "hints": ["Look at the lines with `>` in the diff.", "Type `diff history/original/nightly_backup.sh norrsken/jobs/nightly_backup.sh`. The date is in the line with `[[ ... ]]`."],
         "sol": ["diff history/original/nightly_backup.sh norrsken/jobs/nightly_backup.sh", ("svar", "2026-09-28")], "ans": "2026-09-28", "xp": 15,
         "after": "28 September, at 23:53. The backup took its last complete copy and the next night the archive was empty. Nobody checked."},
        {"text": "Sofia deleted the folder `.notes` from her home folder, but it still exists in the backup `backup/nightly_2026-09-28.tar.gz`. Create the folder `evidence` and unpack the whole of `.notes` into it.",
         "hints": ["`tar -tzf` lists the archive contents. Filter with `grep notes` to see the path.", "`tar -xzf archive -C evidence path` unpacks a folder there. The path starts with `homes/`.",
                   "`mkdir evidence` and then `tar -xzf backup/nightly_2026-09-28.tar.gz -C evidence homes/sholm/.notes`."],
         "sol": ["mkdir evidence", "tar -tzf backup/nightly_2026-09-28.tar.gz | grep notes",
                 "tar -xzf backup/nightly_2026-09-28.tar.gz -C evidence homes/sholm/.notes"],
         "check": _restored_both, "xp": 35,
         "after": "A backup is evidence. What was deleted afterwards is still there."},
        {"text": "Read `plan.txt`. The contact at the competing company has a first name. What is it?",
         "hints": ["The file is under `evidence`, at the same path as in the archive.", "Type `cat evidence/homes/sholm/.notes/plan.txt`."],
         "sol": ["cat evidence/homes/sholm/.notes/plan.txt", ("svar", "Erik")], "ans": "Erik", "xp": 10,
         "after": "Erik at competitor-x. The same Erik Falk sent the plan to."},
        {"text": "Read `payments.csv` in the evidence folder. How much was Sofia promised in total? Sum the column `amount` for her rows.",
         "hints": ["Filter the rows with `grep sholm`. Sum with `awk`.", "`awk -F, '{s+=$3} END{print s}'` sums column 3. Pipe the filtered rows into it.",
                   "Type `grep sholm evidence/homes/sholm/.notes/payments.csv | awk -F, '{s+=$3} END{print s}'`."],
         "sol": ["grep sholm evidence/homes/sholm/.notes/payments.csv | awk -F, '{s+=$3} END{print s}'", ("svar", "250000")], "ans": ["250000", "250,000"], "xp": 30,
         "after": "250,000 kronor, in three parts. That is roughly what half a year of salary costs at Fyrtornet."},
        {"text": "How much was Lena Falk promised? Answer with the amount in kronor.",
         "hints": ["The same file. Search for her username.", "Type `grep lfalk evidence/homes/sholm/.notes/payments.csv`."],
         "sol": ["grep lfalk evidence/homes/sholm/.notes/payments.csv", ("svar", "40000")], "ans": ["40000", "40,000"], "xp": 10,
         "after": "40,000 kronor for doing what she was told was a consulting job. She never needed to know more. That was the whole point."},
    ],
}

# ------------------------------------------------------------ case 5: the clock is ticking


def build15(g):
    r = random.Random(15 * 1000003 + g.seed)
    casebook(g, [
        "Sofia Holm (sholm) used Maria's account (mbergman) from her laptop LT-0417 and planted sabotage in purge_old_data.sh and nightly_backup.sh.",
        "She copied Maria's private key and deleted her tracks. The note was in the backup.",
        "Competitor-x is paying. Lena Falk was tricked with a fake consulting job, as cover.",
        "The sabotage code may have been copied to more scripts. The hidden string starts with " + BLOB_KEY_EN + " and can be searched for in norrsken and homes.",
        "The latest complete backup is nightly_2026-09-28. Changes after that exist only in binlog.",
    ])
    rows = orders()
    base = rows[:BASE_ROWS]
    ins = rows[BASE_ROWS:]
    W(g, "norrsken/data/customers.csv", customers_csv())
    targz(g, "backup/nightly_2026-09-28.tar.gz", {"preorders.csv": CSV_HEAD_EN + csv_rows(base), "customers.csv": customers_csv()}, "2026-09-28")
    for d in days("2026-09-29", "2026-10-15"):
        empty_file(g, "backup/nightly_%s.tar.gz" % d, d)
    # binlog
    fmt = "%Y-%m-%d %H:%M:%S"
    t0 = datetime.datetime(2026, 9, 29)
    span = int((datetime.datetime(2026, 10, 15, 3, 11) - t0).total_seconds())
    stamps = sorted(t0 + datetime.timedelta(seconds=r.randint(0, span)) for _ in ins)
    per = {}
    for row, ts in zip(ins, stamps):
        per.setdefault(ts.date().isoformat(), []).append((ts, "INSERT preorders %d,%s,%s,%d" % row))
    for d in days("2026-09-29", "2026-10-15"):
        ev = list(per.get(d, []))
        day0 = datetime.datetime.fromisoformat(d)
        cut = 3 * 3600 + 12 * 60 if d == "2026-10-15" else 86399
        for _ in range(r.randint(80, 140)):
            ts = day0 + datetime.timedelta(seconds=r.randint(0, cut))
            k = r.random()
            if k < 0.5:
                ev.append((ts, "UPDATE customers %d" % r.randint(1, 60)))
            elif k < 0.85:
                ev.append((ts, "INSERT orders %d,%d" % (r.randint(10000, 99999), r.randint(1, 60))))
            else:
                ev.append((ts, "DELETE sessions %d" % r.randint(2, 300)))
        if d == "2026-10-15":
            ev.append((day0 + datetime.timedelta(seconds=3 * 3600 + 12 * 60 + 9), "DELETE preorders ALL rows=%d" % TOTAL_ROWS))
        ev.sort(key=lambda e: e[0])
        out = ["# binlog %s" % d]
        for ts, msg in ev:
            out.append("%s %s" % (ts.strftime(fmt), msg))
        if d == "2026-10-15":
            g.S["del_line"] = str([i + 1 for i, l in enumerate(out) if "DELETE preorders ALL" in l][0])
        W(g, "binlog/%s.sql" % d, "\n".join(out) + "\n")
    g.S["ins"] = str(len(ins))
    g.S["expected"] = CSV_HEAD_EN + csv_rows(rows)
    g.S["base_expected"] = CSV_HEAD_EN + csv_rows(base)

    # sabotage copies
    def infect(name, body):
        return "#!/bin/bash\n# " + name + "\n" + body + '_k="' + BLOB_EN + '"\n_c="$(printf \'%s\' "$_k" | base64 -d)"\neval "$_c"\n'
    W(g, "norrsken/jobs/stats.sh", infect("stats.sh", "echo statistics\n"), mode=0o755)
    W(g, "norrsken/jobs/flush_mail_queue.sh", infect("flush_mail_queue.sh", "echo mail queue\n"), mode=0o755)
    W(g, "norrsken/config/profile.d/zz_compat.sh", infect("zz_compat.sh", ""), mode=0o644)
    W(g, "homes/mbergman/.profile", infect(".profile", "export EDITOR=vim\n"), mode=0o644)
    W(g, "norrsken/jobs/fetch_cert.sh",
      '#!/bin/bash\n# fetches the certificate and decodes it\ncert="LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0t"\necho "$cert" | base64 -d > "$HOME/norrsken/config/cert.pem"\n', mode=0o755)
    W(g, "norrsken/jobs/rotate_logs.sh", "#!/bin/bash\n# rotate_logs.sh\necho rotate\n", mode=0o755)
    W(g, "norrsken/jobs/clear_cache.sh", "#!/bin/bash\n# clear_cache.sh\necho cache\n", mode=0o755)
    for u in ("tnilsson", "jekberg", "pwallin", "sholm"):
        W(g, "homes/%s/.profile" % u, "export EDITOR=vim\n")
    g.S["infected"] = "4"


def _no_blob_left(g):
    for top in ("norrsken", "homes"):
        base = g.P(top)
        for d, _, fs in os.walk(base):
            for f in fs:
                try:
                    with open(os.path.join(d, f), encoding="utf-8", errors="ignore") as h:
                        if BLOB_EN in h.read():
                            return False
                except OSError:
                    pass
    return True


INFECTED = {"stats.sh", "flush_mail_queue.sh", "zz_compat.sh", ".profile"}


def _quarantine5(g):
    k = g.P("quarantine")
    if not os.path.isdir(k):
        return False
    return INFECTED <= set(os.listdir(k)) and _no_blob_left(g)


def _restore_base(g):
    return read(g, "norrsken/data/preorders.csv") == g.S["base_expected"]


def _restore_all(g):
    return read(g, "norrsken/data/preorders.csv") == g.S["expected"]


def _incident(g):
    t = read(g, "incident.txt").casefold()
    return (all(x in t for x in ("sholm", "mbergman", "lfalk", "purge_old_data", "competitor-x"))
            and isfile(g, "incident.txt") and (mode(g, "incident.txt") & 0o077) == 0)


L15 = {
    "case": True,
    "title": "The clock is ticking",
    "story": ("Thursday 2026-10-15, 21:40. You know who, how and why. The launch is on Monday and three things are left.\n\n"
              "The first is to clean up after Sofia. She had time to copy the sabotage code to more scripts before she left. "
              "The second is to get the 1,847 customers back. The backup is old, but there is a log of everything that has happened since. "
              "The third is the report.\n\n"
              "\"This is the hard part\", says GUS. \"Finding someone to blame is the easy bit. Fixing it so that nobody notices it ever broke is harder.\""),
    "learn": ("No new commands. It is the same tools, but more of them in the same mission.\n\n"
              "- A `for` loop goes through a list: `for f in $(command); do mv \"$f\" folder/; done`.\n"
              "- `sed 's/.*word //'` removes everything up to and including the word on each line.\n"
              "- `>>` appends to the end of a file. `>` overwrites it.\n"
              "- `binlog/` contains one file per day with every change in the database, in time order."),
    "build": build15,
    "cheats": [("for f in $(cmd); do ...; done", "do something for each match"), ("sed 's/.*word //'", "remove everything before a word"),
               ("grep -h", "show matches without file names"), ("grep -rl word folder", "list files containing the word")],
    "outro": ("GUS: \"The preorders are back, all 1,847. The sabotage code is in quarantine in four places. The report is with Johan.\""),
    "missions": [
        {"text": "The sabotage code may have been copied to more files. Its hidden string starts with `" + BLOB_KEY_EN + "` (see `casebook.txt`). How many files under `norrsken` and `homes` contain it?",
         "hints": ["`grep -r` searches a whole folder and `-l` lists only the file names.", "Search both folders at once. Add `| wc -l` to count.",
                   "Type `grep -rl " + BLOB_KEY_EN + " norrsken homes | wc -l`."],
         "sol": ["grep -rl " + BLOB_KEY_EN + " norrsken homes | wc -l", ("svar", "4")], "ans": "4", "xp": 20,
         "after": "Four copies. One of them sits in Maria's `.profile`, which runs every time she logs in."},
        {"text": "Move the four files to a new folder `quarantine` in your home folder so the sabotage code is not left anywhere else.",
         "hints": ["`mkdir quarantine` first. Then you need to move several files at once.", "A `for` loop can go through the result of `grep -rl`.",
                   "`for f in $(grep -rl " + BLOB_KEY_EN + " norrsken homes); do mv \"$f\" quarantine/; done`."],
         "sol": ["mkdir quarantine", "for f in $(grep -rl " + BLOB_KEY_EN + " norrsken homes); do mv \"$f\" quarantine/; done"], "check": _quarantine5, "xp": 35,
         "after": "Four files in four places. One script that runs every night, one that runs at login and two that just sit there waiting."},
        {"text": "Start the restore. Unpack `preorders.csv` from the backup `backup/nightly_2026-09-28.tar.gz` into `norrsken/data`.",
         "hints": ["`tar -xzf` unpacks. The flag `-C` picks where. Give the file name last.", "Type `tar -xzf backup/nightly_2026-09-28.tar.gz -C norrsken/data preorders.csv`."],
         "sol": ["tar -xzf backup/nightly_2026-09-28.tar.gz -C norrsken/data preorders.csv"], "check": _restore_base, "xp": 20,
         "after": "1,240 preorders are back. 607 are missing."},
        {"text": "All changes since the backup are in `binlog/`, one file per day. New preorders appear as lines with `INSERT preorders`. How many such lines are there in all the files together?",
         "hints": ["`grep -h` searches without printing the file name in front of each line. The glob `*` takes all files.", "Type `grep -h \"INSERT preorders\" binlog/*.sql | wc -l`."],
         "sol": ["grep -h \"INSERT preorders\" binlog/*.sql | wc -l", ("svar", lambda g: g.S["ins"])], "ans": lambda g: g.S["ins"], "xp": 20,
         "after": "607 new preorders over 17 days. That number plus 1,240 makes 1,847."},
        {"text": "The log `binlog/2026-10-15.sql` also contains the line that deleted all the preorders. It must not be replayed. Which line is it on? Answer with the line number.",
         "hints": ["Search for `DELETE preorders` and show line numbers.", "Type `grep -n \"DELETE preorders\" binlog/2026-10-15.sql`."],
         "sol": ["grep -n \"DELETE preorders\" binlog/2026-10-15.sql", ("svar", lambda g: g.S["del_line"])], "ans": lambda g: g.S["del_line"], "xp": 20,
         "after": "Only `INSERT preorders` goes into the file. Everything else, including the `DELETE` line, stays out."},
        {"text": "Finish `norrsken/data/preorders.csv`. Append all the `INSERT preorders` lines from `binlog/` to the end of the file, without date, time and the word INSERT. The file should only have id, email, product and quantity, exactly like the rows already in it.",
         "hints": ["`grep -h` picks the lines. `sed` can remove everything before `INSERT preorders `. `>>` appends.", "The order of the files matters. `binlog/*.sql` is already sorted by date.",
                   "`grep -h \"INSERT preorders\" binlog/*.sql | sed 's/.*INSERT preorders //' >> norrsken/data/preorders.csv`."],
         "sol": ["grep -h \"INSERT preorders\" binlog/*.sql | sed 's/.*INSERT preorders //' >> norrsken/data/preorders.csv"], "check": _restore_all, "xp": 40,
         "after": "All the preorders in the right order. You ran the same log the database would have run, except you skipped the delete."},
        {"text": "How many preorders does the restored file contain? Do not count the header row.",
         "hints": ["`wc -l` counts lines, including the header.", "Type `wc -l norrsken/data/preorders.csv` and subtract one."],
         "sol": ["wc -l norrsken/data/preorders.csv", ("svar", str(TOTAL_ROWS))], "ans": [str(TOTAL_ROWS), "1,847"], "xp": 15,
         "after": "1,847, the same number the database deleted. No customer has gone missing."},
        {"text": "Write the report. Create `incident.txt` that mentions the guilty person (username), the account that was abused, the script the sabotage code was in, the company that paid and the person used as cover. Make the file readable only by you.",
         "hints": ["`echo` and `>` create the file. `chmod 600` makes it private.", "Include `sholm`, `mbergman`, `purge_old_data`, `competitor-x` and `lfalk`.",
                   "Type `echo \"sholm used the account mbergman to plant sabotage in purge_old_data.sh. Competitor-x paid. lfalk was used as cover.\" > incident.txt` and then `chmod 600 incident.txt`."],
         "sol": ["echo \"sholm used the account mbergman to plant sabotage in purge_old_data.sh. Competitor-x paid. lfalk was used as cover.\" > incident.txt",
                 "chmod 600 incident.txt"], "check": _incident, "xp": 40,
         "after": "A report that names who, how and why, and that only you can read. Now Johan can take it from here."},
    ],
}

CASES = [L11, L12, L13, L14, L15]

EPILOGUE = (
    "GUS: \"Sofia Holm was picked up on Friday morning. Erik at competitor-x got a letter from Fyrtornet's lawyer. "
    "Lena Falk has had a long talk with HR and has been told how much she was really worth to them. "
    "Norrsken launched on Monday with all 1,847 preorders in place.\"\n\n"
    "\"You started on Wednesday by learning what a folder is. You ended by defusing a time bomb, "
    "tracking down a hacked account and restoring a database from a log. You did it without clicking once.\"\n\n"
    "GUS adds: \"I have no more cases for you. But more will come. They always do.\""
)
