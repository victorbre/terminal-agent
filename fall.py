# -*- coding: utf-8 -*-
"""Kapitel 2: Mörkläggningen. Fem fall som bygger på varandra.

Samma uppbyggnad som levels.py. Varje fall har "case": True så att spelet
visar "Fall" i stället för "Nivå" och räknar rang för sig.

Tidslinjen (2026):
  09-28 23.47  Lena Falk läcker Norrsken-planen (tutorialens fall)
  09-28 23.52  Någon loggar in som mbergman och lägger sabotage i två skript
  10-15 03.12  Sabotaget körs. Tabellen preorders töms.
  10-19        Lanseringen. Ett andra sabotage ska radera kunder.csv.
"""
import base64
import datetime
import difflib
import io
import os
import random
import shutil
import subprocess
import tarfile
import time

from levels import W, D, isdir, isfile, read, mode, walk_files, hms  # noqa: F401

# ------------------------------------------------------------ gemensamt

BOMB_DATE = "2026-10-15"
LAUNCH_DATE = "2026-10-19"
BASE_ROWS = 1240      # rader i preorders vid backupen 2026-09-28
INS_ROWS = 607        # rader som lades till efter det, fram till 03.12 den 15 oktober
TOTAL_ROWS = BASE_ROWS + INS_ROWS   # 1847

PAYLOAD = (
    'D="${NORRSKEN_DATA:-$HOME/norrsken/data}"\n'
    'd="$(date +%F)"\n'
    '[ "$d" = "' + BOMB_DATE + '" ] && rm -f "$D/preorders.csv"\n'
    '[ "$d" = "' + LAUNCH_DATE + '" ] && rm -f "$D/kunder.csv"\n'
)
BLOB = base64.b64encode(PAYLOAD.encode()).decode()
BLOB_KEY = BLOB[:5]

USERS = ["lfalk", "tnilsson", "mbergman", "akarlsson", "jekberg", "pwallin", "sholm"]

FIRST = ["anna", "erik", "maja", "olle", "lisa", "karl", "sara", "johan", "emma", "nils", "eva",
         "david", "klara", "oskar", "elin", "filip", "ida", "axel", "mia", "viktor"]
LAST = ["lund", "berg", "strand", "holm", "nord", "sjo", "dahl", "ek", "fors", "wik", "lind",
        "aberg", "sten", "hall", "blom"]


def fallbok(g, facts):
    txt = ("FALLBOK: Mörkläggningen på Fyrtornet AB\n"
           "Förd av GUS. Det som står här har vi redan bevisat.\n\n")
    txt += "\n".join("- " + f for f in facts) + "\n"
    W(g, "fallbok.txt", txt)


def targz(g, rel, files, day=None):
    p = g.P(rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with tarfile.open(p, "w:gz") as t:
        for name, data in files.items():
            if isinstance(data, str):
                data = data.encode("utf-8")
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            ti.mode = 0o644
            ti.mtime = 0
            t.addfile(ti, io.BytesIO(data))
    if day:
        when = time.mktime(time.strptime(day + " 02:00:00", "%Y-%m-%d %H:%M:%S"))
        os.utime(p, (when, when))


def empty_file(g, rel, day):
    p = g.P(rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").close()
    when = time.mktime(time.strptime(day + " 02:00:00", "%Y-%m-%d %H:%M:%S"))
    os.utime(p, (when, when))


def days(start, end):
    a = datetime.date.fromisoformat(start)
    b = datetime.date.fromisoformat(end)
    out = []
    while a <= b:
        out.append(a.isoformat())
        a += datetime.timedelta(days=1)
    return out


def spawn_named(g, rel):
    dst = g.P(rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    src = "/bin/sleep" if os.path.exists("/bin/sleep") else "/usr/bin/sleep"
    shutil.copy(src, dst)
    os.chmod(dst, 0o755)
    subprocess.run(["codesign", "--force", "-s", "-", dst], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    p = subprocess.Popen([dst, "100000"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    g.procs.append(p)
    g.S["pid"] = p.pid


def killed(g):
    return bool(g.procs) and g.procs[0].poll() is not None


def orders():
    """Alla 1 847 förbeställningar. Samma varje gång spelet byggs."""
    r = random.Random(500)
    prod = ["Norrsken Bas", "Norrsken Pro", "Norrsken Team"]
    return [(i, "%s.%s%d@example.se" % (r.choice(FIRST), r.choice(LAST), i % 97), r.choice(prod), r.randint(1, 5))
            for i in range(1, TOTAL_ROWS + 1)]


def csv_rows(rows):
    return "".join("%d,%s,%s,%d\n" % row for row in rows)


CSV_HEAD = "id,epost,produkt,antal\n"


def customers_csv():
    r = random.Random(501)
    rows = ["id,namn,epost,kundtyp"]
    for i in range(1, 61):
        rows.append("%d,%s %s,%s.%s@kund%d.example,%s" % (
            i, r.choice(FIRST).capitalize(), r.choice(LAST).capitalize(),
            r.choice(FIRST), r.choice(LAST), i, r.choice(["företag", "privat", "reseller"])))
    return "\n".join(rows) + "\n"


# ------------------------------------------------------------ fall 1: nattlarmet

INFO = [("app", "begäran klar på %d ms", (40, 380)), ("web", "sida levererad, status 200", None),
        ("db", "fråga klar på %d ms", (2, 90)), ("cache", "träffgrad %d procent", (82, 97)),
        ("auth", "inloggning godkänd", None), ("mail", "kön tom", None),
        ("backup", "kontroll ok", None), ("jour", "heartbeat ok", None)]
WARN = [("db", "långsam fråga, %d ms", (400, 1200)), ("web", "svarstid över 800 ms", None),
        ("app", "minnesanvändning %d procent", (78, 89)), ("cache", "utrymme %d procent", (80, 92))]
ERR = [("mail", "leverans misslyckades, nytt försök görs", None),
       ("web", "502 från uppströms, nytt försök lyckades", None),
       ("app", "timeout mot betaltjänsten, nytt försök lyckades", None)]

FALL1_START = 20 * 3600     # loggfönstret börjar 2026-10-14 20.00


def _off(day, h, m, s):
    return (day - 14) * 86400 + h * 3600 + m * 60 + s - FALL1_START


def _stamp(off):
    t = FALL1_START + off
    return "2026-10-%02d %s" % (14 + t // 86400, hms(t % 86400))


def _pick(r, tbl):
    svc, msg, rng = r.choice(tbl)
    if rng:
        msg = msg % r.randint(*rng)
    return svc, msg


def build11(g):
    r = random.Random(11 * 1000003 + g.seed)
    fallbok(g, [
        "Torsdag 2026-10-15, natten. Förbeställningarna av Norrsken syns inte längre och checkouten ligger nere.",
        "Lanseringen är måndag 2026-10-19.",
    ])
    span = _off(15, 9, 0, 0)
    ev = []
    for _ in range(4200):
        x = r.random()
        tbl, lvl = (INFO, "INFO") if x < 0.85 else ((WARN, "WARN") if x < 0.96 else (ERR, "ERROR"))
        svc, msg = _pick(r, tbl)
        ev.append((r.randint(0, span), lvl, svc, msg))
    crisis = [
        (_off(15, 3, 12, 7), "INFO", "cron", "startar jobb rensa_gamla_data"),
        (_off(15, 3, 12, 9), "WARN", "db", "massradering påbörjad i tabellen preorders"),
        (_off(15, 3, 12, 10), "CRITICAL", "db", "tabellen preorders saknar rader"),
        (_off(15, 3, 12, 11), "CRITICAL", "app", "preorder-API svarar 500"),
        (_off(15, 3, 12, 15), "ERROR", "web", "5xx-andel 94 procent"),
        (_off(15, 3, 12, 31), "CRITICAL", "web", "checkout nere"),
        (_off(15, 3, 13, 2), "CRITICAL", "app", "kundvyn kan inte laddas"),
        (_off(15, 3, 14, 2), "INFO", "jour", "larm skickat till jourhavande"),
        (_off(15, 3, 15, 40), "CRITICAL", "cache", "replikering stoppad"),
        (_off(15, 3, 40, 12), "INFO", "jour", "larm kvitterat av pwallin"),
    ]
    ev += crisis
    ev.sort(key=lambda e: e[0])
    W(g, "loggar/monitor.log", "".join("%s %s %s: %s\n" % (_stamp(o), l, s, m) for o, l, s, m in ev))
    g.S["crit"] = str(sum(1 for e in ev if e[1] == "CRITICAL"))
    g.S["first_crit"] = [_stamp(e[0]).split()[1] for e in ev if e[1] == "CRITICAL"][0]

    # cron
    jobs = [("00:30:01", "svc_batch", "rotera_loggar.sh"), ("01:00:01", "svc_stat", "statistik.sh"),
            ("02:00:01", "svc_backup", "backup_natt.sh"), ("03:12:07", "svc_batch", "rensa_gamla_data.sh"),
            ("04:00:01", "svc_mail", "mailko_tomning.sh"), ("05:30:01", "svc_web", "cache_tomning.sh")]
    cl = []
    for d in range(9, 16):
        for t, u, s in jobs:
            cl.append("Oct %02d %s CRON[%d]: (%s) CMD (norrsken/jobb/%s)" % (d, t, r.randint(1200, 9800), u, s))
    W(g, "loggar/cron.log", "\n".join(cl) + "\n")

    # databas
    dl = []
    tables_read = ["kunder", "ordrar", "preorders", "produkter"]
    for _ in range(3800):
        off = r.randint(0, _off(15, 3, 12, 0))
        x = r.random()
        if x < 0.62:
            op = "SELECT FROM %s rows=%d" % (r.choice(tables_read), r.randint(1, 40))
            u = "svc_app"
        elif x < 0.74:
            op = "INSERT INTO ordrar rows=1"
            u = "svc_app"
        elif x < 0.82:
            op = "INSERT INTO preorders rows=1"
            u = "svc_web"
        elif x < 0.92:
            op = "UPDATE kunder rows=1"
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
    W(g, "loggar/db.log", "".join(x[1] + "\n" for x in dl))
    g.S["rows"] = str(TOTAL_ROWS)

    # backuper
    empties = 0
    allrows = orders()
    for d in days("2026-09-14", "2026-10-15"):
        rel = "backup/natt_%s.tar.gz" % d
        if d <= "2026-09-28":
            n = 900 + len(days("2026-09-14", d)) * 22
            targz(g, rel, {"preorders.csv": CSV_HEAD + csv_rows(allrows[:n])}, d)
        else:
            empty_file(g, rel, d)
            empties += 1
    g.S["empty"] = str(empties)

    spawn_named(g, "norrsken/verktyg/natt_rensare")


def _tidslinje(g):
    t = read(g, "tidslinje.txt").casefold()
    import re
    return bool(re.search(r"03[:.]12", t)) and "rensa_gamla_data" in t and "svc_batch" in t


L11 = {
    "case": True,
    "title": "Nattlarmet",
    "chapter": ("KAPITEL 2: MÖRKLÄGGNINGEN",
                "Falk-utredningen är sjutton dagar gammal och rapporten ligger hos chefen. Ingen på Fyrtornet "
                "tänker längre på den. Det gör du inte heller, tills din jourtelefon ringer.\n\n"
                "Från och med nu får du inga lektioner. Uppdragen frågar efter vad du ska ta reda på, "
                "inte vilket kommando du ska köra. Du väljer verktyg själv. `hint` finns kvar när du kör fast."),
    "story": ("Torsdag 2026-10-15, kl. 03.40. Det är GUS i luren. \"Förbeställningarna av Norrsken är borta. "
              "Checkouten ligger nere. Lanseringen är på måndag.\"\n\n"
              "Johan Ekberg, IT-chefen, har skrivit i chatten: \"Ta reda på vad som hände, när det hände och varför "
              "ingen märkte något i förväg. Börja med loggarna. Titta på backuperna sedan.\"\n\n"
              "GUS har lagt loggarna i `loggar` och backuperna i `backup`. I din hemmapp ligger `fallbok.txt`. "
              "Det är hans anteckningsblock, och det fylls på för varje sak du bevisar."),
    "learn": ("Verktygen är de du redan har: `ls`, `cat`, `head`, `tail`, `grep`, `find`, `wc`, `sort`, `uniq` och rören mellan dem. "
              "Loggarna är långa. Läs dem inte rad för rad, sök på det du vet.\n\n"
              "Ett sätt att börja är att utgå från en tid eller ett namn, söka på det och följa nästa spår. "
              "`grep A fil | grep B` hittar rader med både A och B."),
    "build": build11,
    "cheats": [("grep A fil | grep B", "rader med både A och B"), ("find mapp -type f -size 0", "hitta tomma filer"),
               ("find mapp -type f -size +0", "hitta filer som inte är tomma")],
    "outro": ("GUS: \"Kl. 03.12 startade rensa_gamla_data som svc_batch och tömde preorders. Backuperna har varit tomma sedan "
              "29 september. Det jobbet har kört varje natt i veckor och aldrig gjort något konstigt. Något i det har ändrats. "
              "Vi öppnar skriptet.\""),
    "missions": [
        {"text": "Börja i `loggar/monitor.log`. Övervakningen markerar de allvarligaste raderna med ordet `CRITICAL`. Hur många sådana rader finns?",
         "hints": ["`grep` kan räkna träffar åt dig.", "Flaggan för att räkna rader är `-c`.", "Skriv `grep -c CRITICAL loggar/monitor.log`."],
         "sol": ["grep -c CRITICAL loggar/monitor.log", ("svar", lambda g: g.S["crit"])], "ans": lambda g: g.S["crit"], "xp": 10,
         "after": "Fem allvarliga rader bland över fyratusen. Resten är brus, och det är därför man söker i stället för att läsa."},
        {"text": "Vilket klockslag har den första `CRITICAL`-raden? Svara med tiden inklusive sekunder, till exempel `12:34:56`.",
         "hints": ["Loggen ligger i tidsordning. Första träffen är den tidigaste.", "`head -n 1` visar bara första raden. Skicka `grep`-resultatet genom det.",
                   "Skriv `grep CRITICAL loggar/monitor.log | head -n 1`."],
         "sol": ["grep CRITICAL loggar/monitor.log | head -n 1", ("svar", lambda g: g.S["first_crit"])], "ans": lambda g: g.S["first_crit"], "xp": 10,
         "after": "Tre sekunder efter att något startade. Loggen visar rad för rad hur det gick sönder."},
        {"text": "Något startade några sekunder före det första larmet. Ta reda på vad det var och vilket konto som körde det. "
                 "Skriv sedan tidslinjen i `tidslinje.txt` i din hemmapp: klockslaget, jobbets namn och kontot.",
         "hints": ["Schemalagda jobb loggas i en egen fil under `loggar`. Sök på datum och klockslag i den.",
                   "Cron-loggen skriver datumet som `Oct 15`. Skriv `grep \"Oct 15 03:12\" loggar/cron.log`. Kontot står inom parentes och skriptet sist.",
                   "Skriv `echo \"03:12 rensa_gamla_data svc_batch\" > tidslinje.txt`."],
         "sol": ["grep \"Oct 15 03:12\" loggar/cron.log", "echo \"03:12 rensa_gamla_data svc_batch\" > tidslinje.txt"], "check": _tidslinje, "xp": 35,
         "after": "Jobbet har kört kl. 03.12 varje natt i veckor, som systemkontot `svc_batch`. Ingen människa loggar in som det, så kontot säger inget om vem som ligger bakom."},
        {"text": "Hur många förbeställningar raderades under natten? Svara med antalet.",
         "hints": ["Databasen har en egen logg under `loggar`. Du söker efter en radering i en viss tabell. Länka två `grep` med ett rör.",
                   "Skriv `grep DELETE loggar/db.log | grep preorders`.",
                   "Antalet står efter `rows=` på raden som gäller `DELETE FROM preorders`."],
         "sol": ["grep DELETE loggar/db.log | grep preorders", ("svar", lambda g: g.S["rows"])], "ans": lambda g: g.S["rows"], "xp": 20,
         "after": "1 847 kunder som betalat i förskott, på en sekund. Det är antalet vi ska ha tillbaka."},
        {"text": "Johan vill veta om det finns något att återställa från. En backup som misslyckats blir en tom fil. Hur många backuper är tomma?",
         "hints": ["Backuperna ligger i en egen mapp. `find` kan filtrera på storlek, och noll är också en storlek.", "Skriv `find backup -type f -size 0` och räkna raderna.",
                   "`find backup -type f -size 0 | wc -l` ger antalet direkt."],
         "sol": ["find backup -type f -size 0 | wc -l", ("svar", lambda g: g.S["empty"])], "ans": lambda g: g.S["empty"], "xp": 15,
         "after": "Sjutton nätter i rad utan backup, och övervakningen skrev \"kontroll ok\" varje natt. Den frågan tar vi senare."},
        {"text": "Vilken är den senaste backupen som inte är tom? Svara med filnamnet.",
         "hints": ["Filnamnen börjar med datum, så en sortering ger tidsordning.", "Filtrera med `-size +0`, sortera och ta sista raden.",
                   "Skriv `find backup -type f -size +0 | sort | tail -n 1`."],
         "sol": ["find backup -type f -size +0 | sort | tail -n 1", ("svar", "natt_2026-09-28.tar.gz")], "ans": ["natt_2026-09-28.tar.gz", "2026-09-28"], "xp": 20,
         "after": "Den 28 september, samma dag som Falk-läckan. Mörkläggningen började med andra ord den kvällen."},
        {"text": "Processen `natt_rensare` kör fortfarande i bakgrunden. Ingen har startat den med avsikt. Stäng ner den.",
         "hints": ["`pgrep` ger PID och `kill` stänger. Du gjorde det med `spok`.", "Skriv `kill $(pgrep natt_rensare)`."],
         "sol": ["kill $(pgrep natt_rensare)"], "check": killed, "xp": 20,
         "after": "En sak mindre som kan gå fel medan du utreder."},
    ],
}

# ------------------------------------------------------------ fall 2: bomben

def _rensa_base():
    return (
        '#!/bin/bash\n'
        '# rensa_gamla_data.sh v2.2\n'
        '# Städar gamla sessioner och temporärfiler. Körs 03.12 varje natt av svc_batch.\n'
        'set -u\n'
        'DATA="${NORRSKEN_DATA:-$HOME/norrsken/data}"\n'
        'TMP="$DATA/tmp"\n'
        'LOG="$HOME/loggar/rensa.log"\n'
        'KEEP_DAYS=14\n'
        '\n'
        'log() {\n'
        '  echo "$(date \'+%F %T\') $*" >> "$LOG"\n'
        '}\n'
        '\n'
        'rensa_tmp() {\n'
        '  [ -d "$TMP" ] || return 0\n'
        '  find "$TMP" -type f -name \'*.tmp\' -mtime +"$KEEP_DAYS" -delete\n'
        '  log "tmp rensad"\n'
        '}\n'
        '\n'
        'rensa_sessioner() {\n'
        '  [ -d "$DATA/sessions" ] || return 0\n'
        '  find "$DATA/sessions" -type f -mtime +7 -delete\n'
        '  log "sessioner rensade"\n'
        '}\n'
        '\n'
        'rensa_cache() {\n'
        '  [ -d "$DATA/cache" ] || return 0\n'
        '  find "$DATA/cache" -type f -mtime +3 -delete\n'
        '  log "cache rensad"\n'
        '}\n'
        '\n'
        'main() {\n'
        '  log "start"\n'
        '  rensa_tmp\n'
        '  rensa_sessioner\n'
        '  rensa_cache\n'
        '  log "klart"\n'
        '}\n'
        '\n'
        'main "$@"\n'
    )


def _rensa_bomb():
    base = _rensa_base()
    block = ('# kompatibilitet med nya lagringsnoden (v2.3)\n'
             '_k="' + BLOB + '"\n'
             '_c="$(printf \'%s\' "$_k" | base64 -d)"\n'
             'eval "$_c"\n'
             'unset _k _c\n'
             '\n')
    return base.replace("main() {", block + "main() {", 1)


def _backup_base():
    return ('#!/bin/bash\n'
            '# backup_natt.sh v1.4\n'
            '# Packar datamappen till backup/natt_DATUM.tar.gz. Körs 02.00 av svc_backup.\n'
            'DATA="${NORRSKEN_DATA:-$HOME/norrsken/data}"\n'
            'OUT="$HOME/backup/natt_$(date +%F).tar.gz"\n'
            'tar -czf "$OUT" -C "$DATA" .\n'
            'echo "$(date \'+%F %T\') backup klar: $OUT" >> "$HOME/loggar/backup.log"\n')


def _backup_bomb():
    return _backup_base().replace(
        'echo "$(date',
        '# rotera arkiv efter 28 sept\n'
        '[[ "$(date +%F)" > "2026-09-28" ]] && : > "$OUT"\n'
        'echo "$(date', 1)


def _added(a, b):
    return sum(1 for l in difflib.ndiff(a.splitlines(), b.splitlines()) if l.startswith("+ "))


def _history(r, added):
    files = ["rotera_loggar.sh", "statistik.sh", "backup_natt.sh", "mailko_tomning.sh", "cache_tomning.sh", "kontroll_backup.sh"]
    who = ["tnilsson", "jekberg", "pwallin", "akarlsson"]
    msgs = ["justerar loggnivå", "rättar sökväg", "tar bort gammal kod", "byter till nya noden", "kommentarer",
            "fixar felmeddelande", "timeout höjd", "städar variabler"]
    rows = []
    for _ in range(600):
        d = (datetime.date(2026, 1, 5) + datetime.timedelta(days=r.randint(0, 280))).isoformat()
        rows.append("%s %02d:%02d %s %s %s (+%d -%d)" % (d, r.randint(8, 17), r.randint(0, 59), r.choice(who),
                                                         r.choice(files), r.choice(msgs), r.randint(1, 9), r.randint(0, 6)))
    rows.append("2026-06-03 10:14 jekberg rensa_gamla_data.sh v2.2 (+12 -3)")
    rows.append("2026-03-19 13:40 tnilsson rensa_gamla_data.sh justerar loggnivå (+1 -1)")
    rows.append("2026-09-28 23:52 mbergman rensa_gamla_data.sh compat-fix v2.3 (+%d -0)" % added)
    rows.append("2026-09-28 23:53 mbergman backup_natt.sh compat-fix v1.5 (+2 -0)")
    rows.sort()
    return "\n".join(rows) + "\n"


def build12(g):
    r = random.Random(12 * 1000003 + g.seed)
    fallbok(g, [
        "Kl. 03.12.07 den 2026-10-15 startade cron-jobbet rensa_gamla_data som svc_batch.",
        "Jobbet raderade alla rader i tabellen preorders.",
        "Nattbackuperna har varit tomma sedan 2026-09-29. Den senaste hela backupen är natt_2026-09-28.",
    ])
    base = _rensa_base()
    bomb = _rensa_bomb()
    added = _added(base, bomb)
    W(g, "norrsken/jobb/rensa_gamla_data.sh", bomb, mode=0o755)
    W(g, "historik/original/rensa_gamla_data.sh", base)
    for n, body in (("rotera_loggar.sh", "rotate loggar\n"), ("statistik.sh", "beräkna statistik\n"),
                    ("mailko_tomning.sh", "töm mailkön\n"), ("cache_tomning.sh", "töm cache\n"),
                    ("kontroll_backup.sh", "kontrollera backup\n"), ("backup_natt.sh", _backup_bomb())):
        W(g, "norrsken/jobb/" + n, "#!/bin/bash\n# " + n + "\n" + body if n != "backup_natt.sh" else body, mode=0o755)
    cron = ["# m h dom mon dow  användare  kommando",
            "30 0 * * *  svc_batch   norrsken/jobb/rotera_loggar.sh",
            "0 1 * * *   svc_stat    norrsken/jobb/statistik.sh",
            "0 2 * * *   svc_backup  norrsken/jobb/backup_natt.sh",
            "12 3 * * *  svc_batch   norrsken/jobb/rensa_gamla_data.sh",
            "0 4 * * *   svc_mail    norrsken/jobb/mailko_tomning.sh",
            "",
            "# veckojobb",
            "30 5 * * *  svc_web     norrsken/jobb/cache_tomning.sh",
            "0 6 * * 1   svc_stat    norrsken/jobb/statistik.sh --vecka",
            "15 6 * * *  svc_backup  norrsken/jobb/kontroll_backup.sh",
            "# 0 7 * * 1  svc_batch   norrsken/jobb/gammalt_jobb.sh",
            "0 12 1 * *  svc_batch   norrsken/jobb/rotera_loggar.sh --manad"]
    W(g, "norrsken/konfig/crontab.txt", "\n".join(cron) + "\n")
    g.S["jobs"] = str(sum(1 for l in cron if l.strip() and not l.startswith("#")))
    g.S["ncron"] = len(cron)
    g.S["lines"] = str(bomb.count("\n"))
    g.S["added"] = str(added)
    W(g, "historik/andringar.log", _history(r, added))
    W(g, "norrsken/data/kunder.csv", customers_csv())


def _cron_fixed(g):
    t = read(g, "ny_crontab.txt")
    if not t or "rensa_gamla_data" in t:
        return False
    return len(t.splitlines()) == g.S["ncron"] - 1


def _quarantined_rensa(g):
    p = "karantan/rensa_gamla_data.sh"
    return isfile(g, p) and (mode(g, p) & 0o111) == 0 and not isfile(g, "norrsken/jobb/rensa_gamla_data.sh")


L12 = {
    "case": True,
    "title": "Bomben",
    "story": ("GUS har lagt skripten från `norrsken/jobb` i din hemmapp, tillsammans med crontab och ändringshistoriken. "
              "\"Ett skript som gjort samma sak varje natt i två år gör inte plötsligt något annat av sig själv\", säger han. "
              "\"Någon har skrivit i det. Hitta vad, och när.\"\n\n"
              "Det finns dessutom en sak till som inte går ihop. Jobbet raderade en fil den 15 oktober. "
              "Om någon planerat det så noga finns det troligen fler datum."),
    "learn": ("Två nya verktyg.\n"
              "- `diff a b` visar skillnaden mellan två filer. Rader med `>` finns bara i den andra filen och rader med `<` bara i den första.\n"
              "- `base64 -d` avkodar text som gömts som base64. Skicka texten genom ett rör: `echo TEXT | base64 -d`. "
              "Det är ingen kryptering. Texten blir bara svår att se för den som skummar.\n\n"
              "`grep -v ord` gör tvärtom mot `grep`: den visar rader utan ordet."),
    "build": build12,
    "cheats": [("diff a b", "visa skillnader mellan två filer"), ("echo TEXT | base64 -d", "avkoda base64"),
               ("grep -v ord fil", "visa rader utan ordet"), ("chmod -x fil", "ta bort körrätten")],
    "outro": ("GUS: \"Bomben hade två datum. Idag var den 15:e, och den 19:e hade kunder.csv försvunnit på lanseringsdagen. "
              "Nu är den avväpnad. Ändringen gjordes av mbergman kl. 23.52 den 28 september, fem minuter efter Falk. "
              "Maria Bergman är utvecklingschef och har inte skrivit i ett städskript på tolv år. Det här är inte hennes verk.\""),
    "missions": [
        {"text": "Öppna `norrsken/konfig/crontab.txt`. Hur många jobb är schemalagda? Rader som börjar med `#` är kommentarer och räknas inte.",
         "hints": ["Ta bort kommentarerna med `grep -v` och räkna resten. Tomma rader ska inte räknas.", "Skriv `grep -v \"^#\" norrsken/konfig/crontab.txt | grep -c .`."],
         "sol": ["grep -v \"^#\" norrsken/konfig/crontab.txt | grep -c .", ("svar", lambda g: g.S["jobs"])], "ans": lambda g: g.S["jobs"], "xp": 10,
         "after": "Nio jobb kör i mörkret varje dygn. Ett av dem hade fått en främmande gäst."},
        {"text": "Hur många rader har `norrsken/jobb/rensa_gamla_data.sh`?",
         "hints": ["Ett kommando räknar rader, ord och tecken i en fil.", "Skriv `wc -l norrsken/jobb/rensa_gamla_data.sh`."],
         "sol": ["wc -l norrsken/jobb/rensa_gamla_data.sh", ("svar", lambda g: g.S["lines"])], "ans": lambda g: g.S["lines"], "xp": 10,
         "after": "Ett kort skript. Det borde gå att läsa på en minut, och det är därför få gjorde det."},
        {"text": "Läs skriptet. Det lagrar en lång, kodad sträng i en variabel. Vad heter variabeln?",
         "hints": ["Leta efter något som inte liknar resten av skriptet. Ordet `base64` är ett bra sökord.", "Skriv `grep -n base64 norrsken/jobb/rensa_gamla_data.sh` och läs raden ovanför.",
                   "Den långa strängen ligger på en rad som börjar med variabelnamnet, följt av `=`."],
         "sol": ["cat norrsken/jobb/rensa_gamla_data.sh", ("svar", "_k")], "ans": "_k", "xp": 15,
         "after": "En kort variabel med ett prydligt namn, i ett block som kallas kompatibilitet. Det ser ut som ett sätt att inte väcka frågor."},
        {"text": "Avkoda strängen. Koden raderar en fil om datumet stämmer. Vilken fil raderas den 2026-10-15? Svara med filnamnet.",
         "hints": ["`base64 -d` avkodar. Ge den strängen via ett rör.", "Plocka ut strängen med `grep \"^_k=\" norrsken/jobb/rensa_gamla_data.sh | cut -d'\"' -f2` och skicka den vidare till `base64 -d`.",
                   "Hela raden: `grep \"^_k=\" norrsken/jobb/rensa_gamla_data.sh | cut -d'\"' -f2 | base64 -d`."],
         "sol": ["grep \"^_k=\" norrsken/jobb/rensa_gamla_data.sh | cut -d'\"' -f2 | base64 -d", ("svar", "preorders.csv")], "ans": "preorders.csv", "xp": 30,
         "after": "Fyra rader kod, gömda i ett kompatibilitetsblock. Den som skrev dem visste att ingen läser skript som funkar."},
        {"text": "Koden har ett andra datum med en annan fil. Vilket datum är det? Svara i formen ÅÅÅÅ-MM-DD.",
         "hints": ["Du har redan avkodat texten. Läs den en gång till.", "Kör samma avkodning igen. Det är den andra `[ ... ]`-raden."],
         "sol": ["grep \"^_k=\" norrsken/jobb/rensa_gamla_data.sh | cut -d'\"' -f2 | base64 -d", ("svar", LAUNCH_DATE)], "ans": LAUNCH_DATE, "xp": 20,
         "after": "19 oktober är lanseringsdagen. På den dagen skulle kunder.csv, alltså hela kundregistret, ha försvunnit."},
        {"text": "Ändringshistoriken finns i `historik/andringar.log`. Vem gjorde den senaste ändringen i `rensa_gamla_data.sh`? Svara med användarnamnet.",
         "hints": ["Sök på skriptets namn. Nyare ändringar ligger längst ned.", "Skriv `grep rensa_gamla_data historik/andringar.log | tail -n 1`."],
         "sol": ["grep rensa_gamla_data historik/andringar.log | tail -n 1", ("svar", "mbergman")], "ans": "mbergman", "xp": 15,
         "after": "Maria Bergman, enligt loggen. Ta det med en nypa salt, för en logg visar vilket konto som skrev, inte vem som satt vid tangentbordet."},
        {"text": "Vilket klockslag gjordes ändringen? Svara i formen `hh:mm`.",
         "hints": ["Samma rad i historiken som förut.", "Skriv `grep rensa_gamla_data historik/andringar.log | tail -n 1` och läs tiden."],
         "sol": ["grep rensa_gamla_data historik/andringar.log | tail -n 1", ("svar", "23:52")], "ans": "23:52", "xp": 10,
         "after": "23.52 den 28 september. Lena Falk loggade in kl. 23.47. Fem minuter mellan dem, och ingen tittade på den andra."},
        {"text": "Jämför skriptet med originalet i `historik/original/`. Hur många rader har lagts till?",
         "hints": ["`diff` jämför två filer. Rader som lagts till syns med `>`.", "Skriv `diff historik/original/rensa_gamla_data.sh norrsken/jobb/rensa_gamla_data.sh` och räkna raderna med `>`.",
                   "`grep -c \"^>\"` räknar dem åt dig."],
         "sol": ["diff historik/original/rensa_gamla_data.sh norrsken/jobb/rensa_gamla_data.sh | grep -c \"^>\"", ("svar", lambda g: g.S["added"])], "ans": lambda g: g.S["added"], "xp": 20,
         "after": "Sex rader lades till, inget togs bort. Allt annat i skriptet är orört, vilket är hur man får något att passera en kodgranskning."},
        {"text": "Avväpna bomben. Skapa `ny_crontab.txt` som är en kopia av `norrsken/konfig/crontab.txt` utan raden för `rensa_gamla_data`. Flytta sedan skriptet till en ny mapp `karantan` i din hemmapp och ta bort dess körrätt.",
         "hints": ["`grep -v` plockar bort rader och `>` sparar resultatet. `mkdir` och `mv` sköter mappen.", "`chmod -x` tar bort körrätten.",
                   "Fyra kommandon: `grep -v rensa_gamla_data norrsken/konfig/crontab.txt > ny_crontab.txt`, `mkdir karantan`, `mv norrsken/jobb/rensa_gamla_data.sh karantan/` och `chmod -x karantan/rensa_gamla_data.sh`."],
         "sol": ["grep -v rensa_gamla_data norrsken/konfig/crontab.txt > ny_crontab.txt", "mkdir karantan",
                 "mv norrsken/jobb/rensa_gamla_data.sh karantan/", "chmod -x karantan/rensa_gamla_data.sh"],
         "check": lambda g: _cron_fixed(g) and _quarantined_rensa(g), "xp": 35,
         "after": "Skriptet ligger kvar som bevis, men ingen kan köra det. Crontab-raden är borta. Den 19:e händer ingenting."},
    ],
}

# ------------------------------------------------------------ fall 3: kontot

HOME_IP = {"lfalk": "10.0.3.31", "tnilsson": "10.0.3.14", "mbergman": "10.0.3.12", "akarlsson": "10.0.3.19",
           "jekberg": "10.0.3.11", "pwallin": "10.0.3.16", "sholm": "10.0.3.23"}
MAC_PWALLIN_OLD = "3c:22:fb:0a:91:5e"
MAC_SHOLM = "a4:83:e7:2b:60:1d"


def _mac(r):
    return ":".join("%02x" % r.randint(0, 255) for _ in range(6))


def _auth_lines(r):
    lines = []
    dl = days("2026-09-14", "2026-10-15")
    vac = set(days("2026-09-21", "2026-10-02"))
    wd = lambda d: time.strptime(d, "%Y-%m-%d").tm_wday < 5

    def add(d, sec, act, u, ip):
        lines.append(("%s %s" % (d, hms(sec)), "%s %s %s from %s" % ("%s %s" % (d, hms(sec)), act, u, ip)))

    for d in dl:
        for u in USERS:
            if u == "mbergman" and d in vac:
                continue
            if wd(d):
                n = r.randint(10, 14) if u == "pwallin" else (r.randint(4, 8) if u != "lfalk" else r.randint(2, 4))
            else:
                n = 3 if u == "pwallin" else 0
            for _ in range(n):
                if u == "pwallin" and r.random() < 0.4:
                    st = r.randint(0, 6 * 3600) if r.random() < 0.5 else r.randint(20 * 3600, 23 * 3600)
                else:
                    st = r.randint(7 * 3600, 16 * 3600)
                ip = HOME_IP[u]
                if u == "pwallin" and "2026-09-14" <= d <= "2026-09-22" and r.random() < 0.6:
                    ip = "10.0.3.17"
                add(d, st, "SSH-LOGIN", u, ip)
                add(d, min(86399, st + r.randint(600, 6000)), "SSH-LOGOUT", u, ip)
                if u in ("jekberg", "pwallin", "sholm") and r.random() < 0.3:
                    add(d, min(86399, st + r.randint(60, 500)), "SUDO", u, ip)
    for _ in range(14):
        d = r.choice(dl)
        add(d, r.randint(0, 86399), "SSH-FAIL", r.choice(USERS + ["admin", "root"]), "185.%d.%d.%d" % (r.randint(1, 250), r.randint(1, 250), r.randint(1, 250)))
    # spåren
    add("2026-09-26", 22 * 3600 + 10 * 60 + 41, "SSH-LOGIN", "mbergman", "10.0.3.17")
    add("2026-09-26", 22 * 3600 + 31 * 60 + 9, "SSH-LOGOUT", "mbergman", "10.0.3.17")
    add("2026-09-28", 23 * 3600 + 47 * 60 + 12, "SSH-LOGIN", "lfalk", "185.12.9.77")
    add("2026-09-28", 23 * 3600 + 52 * 60 + 30, "SSH-LOGIN", "mbergman", "10.0.3.17")
    add("2026-09-28", 23 * 3600 + 58 * 60 + 1, "SSH-LOGOUT", "lfalk", "185.12.9.77")
    add("2026-09-29", 14 * 60 + 2, "SSH-LOGOUT", "mbergman", "10.0.3.17")
    add("2026-10-01", 1 * 3600 + 15 * 60 + 9, "SSH-LOGIN", "mbergman", "10.0.3.17")
    add("2026-10-01", 1 * 3600 + 40 * 60 + 33, "SSH-LOGOUT", "mbergman", "10.0.3.17")
    lines.sort(key=lambda x: x[0])
    return [l[1] for l in lines]


def build13(g):
    r = random.Random(13 * 1000003 + g.seed)
    fallbok(g, [
        "Kl. 03.12.07 den 2026-10-15 startade cron-jobbet rensa_gamla_data som svc_batch och raderade alla rader i preorders.",
        "Skriptet innehåller en dold kodbit i base64. Den raderar preorders.csv den 2026-10-15 och kunder.csv på lanseringsdagen.",
        "Skriptet ändrades 2026-09-28 kl. 23.52 med användarkontot mbergman. Skriptet ligger nu i karantän.",
        "Lena Falk loggade in kl. 23.47 samma kväll.",
    ])
    lines = _auth_lines(r)
    W(g, "loggar/auth.log", "\n".join(lines) + "\n")
    lg = [l.split() for l in lines if " SSH-LOGIN " in l]
    cnt = {}
    for p in lg:
        cnt[p[3]] = cnt.get(p[3], 0) + 1
    top = max(cnt, key=cnt.get)
    g.S["top"] = top
    vac = [p for p in lg if p[3] == "mbergman" and "2026-09-21" <= p[0] <= "2026-10-02"]
    g.S["vac"] = str(len(vac))
    W(g, "it/personal.csv",
      "anvandare,namn,roll\n"
      "lfalk,Lena Falk,Marknad\ntnilsson,Tomas Nilsson,Backupansvarig\nmbergman,Maria Bergman,Utvecklingschef\n"
      "akarlsson,Anders Karlsson,Ekonomichef\njekberg,Johan Ekberg,IT-chef\npwallin,Petra Wallin,Drifttekniker\n"
      "sholm,Sofia Holm,Plattformsutvecklare\n")
    W(g, "it/semesterlista.csv",
      "anvandare,fran,till,kommentar\n"
      "tnilsson,2026-07-06,2026-07-24,\nakarlsson,2026-08-03,2026-08-14,\n"
      "mbergman,2026-09-21,2026-10-02,Kanarieöarna\njekberg,2026-07-20,2026-08-07,\n")
    # dhcp
    dh = ["start,slut,ip,mac"]
    for i in list(range(11, 17)) + list(range(18, 41)):
        dh.append("2026-09-01,2026-11-30,10.0.3.%d,%s" % (i, _mac(r)))
    dh.append("2026-09-14,2026-09-22,10.0.3.17,%s" % MAC_PWALLIN_OLD)
    dh.append("2026-09-25,2026-10-05,10.0.3.17,%s" % MAC_SHOLM)
    dh.sort()
    W(g, "it/dhcp.leases", "\n".join(dh) + "\n")
    inv = ["tillgang,typ,mac,tilldelad"]
    for i in range(1, 41):
        inv.append("LT-%04d,bärbar,%s,%s" % (300 + i, _mac(r), r.choice(USERS + ["reserv", "lager"])))
    inv.append("LT-0409,bärbar,%s,pwallin" % MAC_PWALLIN_OLD)
    inv.append("LT-0417,bärbar,%s,sholm" % MAC_SHOLM)
    inv.append("DT-0207,stationär,%s,sholm" % _mac(r))
    W(g, "it/inventarie.csv", "\n".join([inv[0]] + sorted(inv[1:])) + "\n")


def _bevis3(g):
    t = read(g, "bevis.txt").casefold()
    return all(x in t for x in ("sholm", "sofia holm", "10.0.3.17", MAC_SHOLM, "lt-0417"))


L13 = {
    "case": True,
    "title": "Kontot",
    "story": ("Du vet vad som hände och hur. Du vet inte vem. Ändringen gjordes med Maria Bergmans konto kl. 23.52 den 28 september.\n\n"
              "GUS lutar sig mot bordet. \"Maria är utvecklingschef. Hon har aldrig skrivit en rad i ett städskript. "
              "Och hon var på semester.\" Han tystnar. \"Ett konto kan ha använts av någon annan. Vi har inloggningsloggen, "
              "en lista över vilka datorer som fått vilken IP-adress och en inventarielista. Det räcker om du följer en tråd i taget.\""),
    "learn": ("Raderna i `loggar/auth.log` ser ut så här: `datum tid händelse användare from ip`. Fälten skiljs åt av mellanslag.\n\n"
              "- `cut -d' ' -f4` plockar det fjärde fältet. Ändra siffran för att få ett annat.\n"
              "- `sort | uniq -c | sort -rn` räknar hur många gånger varje rad förekommer, med den vanligaste överst.\n"
              "- `grep A fil | grep B` hittar rader med både A och B.\n\n"
              "Mapp `it` innehåller tre listor: DHCP-utdelningar (vilken dator som hade vilken IP mellan vilka datum), "
              "inventarie (vem datorn tillhör) och personal."),
    "build": build13,
    "cheats": [("cut -d' ' -f4", "plocka fält 4, skilt av mellanslag"), ("sort | uniq -c | sort -rn", "räkna förekomster, flest överst"),
               ("grep -E \"a|b\" fil", "rader som matchar a eller b")],
    "outro": ("GUS: \"Någon loggade in som Maria från 10.0.3.17. Den adressen hade en bärbar, LT-0417, den 28 september. "
              "Den bärbara tillhör Sofia Holm, plattformsutvecklare. Inte Maria. Inte Lena Falk, och inte Petra Wallin heller, "
              "trots att hon har flest inloggningar.\""),
    "missions": [
        {"text": "Börja brett. Vilken användare har flest `SSH-LOGIN` i hela `loggar/auth.log`? Svara med användarnamnet.",
         "hints": ["Plocka ut användarnamnet med `cut` och räkna med `sort | uniq -c`.", "Skriv `grep SSH-LOGIN loggar/auth.log | cut -d' ' -f4 | sort | uniq -c | sort -rn`.",
                   "Översta raden har flest."],
         "sol": ["grep SSH-LOGIN loggar/auth.log | cut -d' ' -f4 | sort | uniq -c | sort -rn | head -n 1", ("svar", lambda g: g.S["top"])], "ans": lambda g: g.S["top"], "xp": 20,
         "after": "Petra Wallin har jouren och loggar in på nätterna. Många inloggningar är inte samma sak som konstiga inloggningar."},
        {"text": "Vilken IP-adress loggar `mbergman` normalt in från? Svara med adressen.",
         "hints": ["Samma teknik som förut, men för ett enda konto och för IP-fältet.", "Skriv `grep \"SSH-LOGIN mbergman\" loggar/auth.log | cut -d' ' -f6 | sort | uniq -c | sort -rn`."],
         "sol": ["grep \"SSH-LOGIN mbergman\" loggar/auth.log | cut -d' ' -f6 | sort | uniq -c | sort -rn", ("svar", "10.0.3.12")], "ans": "10.0.3.12", "xp": 15,
         "after": "En adress dominerar. Men det finns fler, och de är få."},
        {"text": "Maria var på semester 2026-09-21 till 2026-10-02 (se `it/semesterlista.csv`). Hur många `SSH-LOGIN` gjorde kontot `mbergman` under semestern?",
         "hints": ["Sök på kontot och på datumen. `grep -E` tillåter alternativ med `|`.", "Datumen börjar med `2026-09-2`, `2026-09-30`, `2026-10-01` eller `2026-10-02`. Länka flera `grep`.",
                   "Ett sätt: `grep \"SSH-LOGIN mbergman\" loggar/auth.log | grep -E \"^2026-(09-(2[1-9]|30)|10-0[12])\" | wc -l`."],
         "sol": ["grep \"SSH-LOGIN mbergman\" loggar/auth.log | grep -E \"^2026-(09-(2[1-9]|30)|10-0[12])\" | wc -l", ("svar", lambda g: g.S["vac"])], "ans": lambda g: g.S["vac"], "xp": 25,
         "after": "Tre inloggningar när ingen var hemma. Antingen jobbade Maria på Kanarieöarna eller så var det någon annan."},
        {"text": "Från vilken IP-adress kom de inloggningarna? Alla tre kom från samma. Svara med adressen.",
         "hints": ["Du har raderna från förra uppdraget. Plocka IP-fältet.", "Lägg till `| cut -d' ' -f6 | sort -u` i slutet av kommandot från förra uppdraget."],
         "sol": ["grep \"SSH-LOGIN mbergman\" loggar/auth.log | grep -E \"^2026-(09-(2[1-9]|30)|10-0[12])\" | cut -d' ' -f6 | sort -u", ("svar", "10.0.3.17")], "ans": "10.0.3.17", "xp": 15,
         "after": "10.0.3.17 dyker upp, och den är inte Marias vanliga adress."},
        {"text": "`it/dhcp.leases` säger vilken dator som hade vilken adress och när. Vilken MAC-adress hade 10.0.3.17 den 28 september? Svara med MAC-adressen.",
         "hints": ["Sök på adressen. Kolla sedan vilken rad vars datum omfattar den 28 september.", "Skriv `grep 10.0.3.17 it/dhcp.leases`. Det finns två rader, för olika perioder."],
         "sol": ["grep 10.0.3.17 it/dhcp.leases", ("svar", MAC_SHOLM)], "ans": MAC_SHOLM, "xp": 25,
         "after": "Adressen bytte ägare den 25 september. Den som tittar på fel rad anklagar fel person."},
        {"text": "`it/inventarie.csv` kopplar MAC-adresser till användare. Vem är datorn tilldelad? Svara med användarnamnet.",
         "hints": ["Sök på MAC-adressen du hittade.", "Skriv `grep -i` följt av adressen och `it/inventarie.csv`."],
         "sol": ["grep -i " + MAC_SHOLM + " it/inventarie.csv", ("svar", "sholm")], "ans": "sholm", "xp": 20,
         "after": "LT-0417, en bärbar dator tilldelad Sofia Holm. Den 28 september kl. 23.52 satt den på adressen som loggade in som Maria."},
        {"text": "Skriv ner beviskedjan. Skapa `bevis.txt` med användarnamn, fullständigt namn (se `it/personal.csv`), IP-adress, MAC-adress och datorns tillgångsnummer.",
         "hints": ["`echo` och `>` skapar filen. Allt kan stå på en rad.", "Namnet får du från `grep sholm it/personal.csv`.",
                   "Skriv `echo \"sholm, Sofia Holm, 10.0.3.17, " + MAC_SHOLM + ", LT-0417\" > bevis.txt`."],
         "sol": ["echo \"sholm, Sofia Holm, 10.0.3.17, " + MAC_SHOLM + ", LT-0417\" > bevis.txt"], "check": _bevis3, "xp": 30,
         "after": "Fem uppgifter som hänger ihop. Det är en beviskedja, och den håller bara om varje länk kan visas."},
        {"text": "Lena Falk loggade in kl. 23.47 den 28 september. Hur många minuter senare loggade kontot `mbergman` in från 10.0.3.17? Svara med antalet.",
         "hints": ["Sök på datum och tid, så ser du raderna intill varandra.", "Skriv `grep \"2026-09-28 23:\" loggar/auth.log`. Räkna ut skillnaden själv."],
         "sol": ["grep \"2026-09-28 23:\" loggar/auth.log", ("svar", "5")], "ans": "5", "xp": 15,
         "after": "Fem minuter. Medan alla tittade på Falk gjorde någon annan sitt jobb."},
    ],
}

# ------------------------------------------------------------ fall 4: spåren

HISTORY_CMDS = [
    "ls", "cd norrsken", "git status", "git pull", "vim jobb/statistik.sh", "docker ps", "tail -f loggar/monitor.log",
    "cd ..", "ls -la", "grep -r timeout loggar", "less loggar/db.log", "make test", "ssh app01", "df -h", "top",
    "cat konfig/crontab.txt", "git log --oneline", "python3 rapport.py", "cd dokument", "history | tail", "npm run build",
    "curl -s localhost:8080/status", "vim README.md", "git commit -am 'fix'", "git push", "which python3", "ps aux | grep nginx",
    "cd ~", "pwd", "free -m", "uptime", "ls dokument", "cat dokument/todo.txt",
]


def build14(g):
    r = random.Random(14 * 1000003 + g.seed)
    fallbok(g, [
        "Kl. 03.12.07 den 2026-10-15 startade rensa_gamla_data och raderade preorders. Skriptet är avväpnat och ligger i karantän.",
        "Skriptet ändrades 2026-09-28 kl. 23.52 med kontot mbergman.",
        "Ändringen gjordes från 10.0.3.17, som hade en bärbar, LT-0417, tilldelad användaren sholm (Sofia Holm).",
        "Maria Bergman var på semester. Hennes konto användes av någon annan.",
    ])
    # sholms hem
    hist = [r.choice(HISTORY_CMDS) for _ in range(640)]
    key = 437
    inc = {
        key - 2: "ls -la /home/mbergman/.ssh/",
        key - 1: "cd /home/mbergman/.ssh",
        key: "cp /home/mbergman/.ssh/id_ed25519 ~/.cache/k",
        key + 1: "chmod 600 ~/.cache/k",
        key + 2: "ssh -i ~/.cache/k mbergman@app01",
        key + 9: "vim norrsken/jobb/rensa_gamla_data.sh",
        key + 10: "vim norrsken/jobb/backup_natt.sh",
        key + 14: "rm ~/.cache/k",
        key + 15: "rm -rf ~/.anteckningar",
    }
    for k, v in inc.items():
        hist[k - 1] = v
    W(g, "hemmappar/sholm/.bash_history", "\n".join(hist) + "\n")
    g.S["key_line"] = str(key)
    W(g, "hemmappar/sholm/dokument/todo.txt", "Uppdatera Docker-bilder.\nBoka tandläkare.\n")
    D(g, "hemmappar/sholm/.cache")
    # mbergman med en nyckel som alla kan läsa
    W(g, "hemmappar/mbergman/.ssh/id_ed25519", "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW\n-----END OPENSSH PRIVATE KEY-----\n", mode=0o644)
    W(g, "hemmappar/mbergman/.ssh/id_ed25519.pub", "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIN0t maria@fyrtornet\n", mode=0o644)
    for u in ("tnilsson", "jekberg", "pwallin", "akarlsson"):
        W(g, "hemmappar/%s/dokument/anteckning.txt" % u, "Möte på fredag.\n")
    # skripten
    W(g, "norrsken/jobb/backup_natt.sh", _backup_bomb(), mode=0o755)
    W(g, "historik/original/backup_natt.sh", _backup_base())
    g.S["diff_added"] = str(_added(_backup_base(), _backup_bomb()))
    # backupen med det raderade
    plan = (
        "PLAN. Radera efter 15/10.\n"
        "- 26/9   Ta Marias nyckel. Hon är på Kanarieöarna till 2/10 och läser inte mejlen.\n"
        "- 28/9 23.45   Falk läcker Norrsken-planen till Erik. Hon tror att det är ett konsultuppdrag (40 000 kr).\n"
        "- 28/9 23.50   Medan alla tittar på Falk: lägg in kompat-blocket i rensa_gamla_data.sh och ändra backupskriptet. Använd Marias konto.\n"
        "- 15/10 03.12  Preorderna försvinner. 19/10 försvinner kunderna. Lanseringen dör.\n"
        "- Erik betalar 250 000 kr totalt, se betalning.csv. Konkurrent-X lanserar sin egen version veckan efter.\n"
        "Kontakt: Erik, konkurrent-x.example. Prata aldrig i Teams.\n"
    )
    pay = ("datum,mottagare,belopp,status\n"
           "2026-09-27,sholm,100000,avtalad\n"
           "2026-10-05,sholm,75000,avtalad\n"
           "2026-10-14,sholm,75000,avtalad\n"
           "2026-09-30,lfalk,40000,avtalad\n")
    files = {
        "hemmappar/sholm/.anteckningar/plan.txt": plan,
        "hemmappar/sholm/.anteckningar/betalning.csv": pay,
        "hemmappar/sholm/dokument/todo.txt": "Uppdatera Docker-bilder.\nBoka tandläkare.\n",
        "hemmappar/tnilsson/dokument/anteckning.txt": "Möte på fredag.\n",
        "hemmappar/mbergman/.ssh/id_ed25519.pub": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIN0t maria@fyrtornet\n",
        "norrsken/data/kunder.csv": customers_csv(),
    }
    targz(g, "backup/natt_2026-09-28.tar.gz", files, "2026-09-28")
    for d in days("2026-09-29", "2026-10-15"):
        empty_file(g, "backup/natt_%s.tar.gz" % d, d)


def _plan_restored(g):
    for p in walk_files(g):
        if os.path.basename(p) == "plan.txt":
            try:
                t = open(p, encoding="utf-8").read()
            except OSError:
                continue
            if "Falk" in t:
                return True
    return False


def _restored_both(g):
    have = {os.path.basename(p) for p in walk_files(g) if "/.anteckningar/" in p or "/bevis/" in p}
    return _plan_restored(g) and "betalning.csv" in have


L14 = {
    "case": True,
    "title": "Spåren efter",
    "story": ("Nu finns det en dator och en ägare. Sofia Holm har tillgång till nästan allt i drift, så tillgång förklarar ingenting. "
              "Frågan är hur hon fick Marias inloggning, vad hon gjorde mer och varför.\n\n"
              "GUS har lagt hennes hemmapp under `hemmappar/sholm`. \"Hon har städat efter sig\", säger han. \"Men backuperna har en "
              "egenskap som människor saknar. De minns allt som fanns när de togs. Den 28 september, den sista hela, "
              "togs före allt det här började.\""),
    "learn": ("Tre nya saker.\n"
              "- `.bash_history` är en fil i hemmappen där skalet sparar vilka kommandon någon har kört, en per rad.\n"
              "- `tar -tzf arkiv.tar.gz` listar innehållet i ett arkiv utan att packa upp det. `tar -xzf arkiv.tar.gz -C mapp sökväg` "
              "packar upp bara en sak i en mapp. Sökvägen ska skrivas som `tar -tzf` visar den.\n"
              "- `awk -F, '{s+=$3} END{print s}' fil` summerar kolumn 3 i en fil med komma mellan värdena.\n\n"
              "Rättigheter har du sett förut. `ls -l` visar vem som får läsa en fil, och `chmod 600` gör den privat."),
    "build": build14,
    "cheats": [("tar -tzf arkiv", "lista innehållet i ett arkiv"), ("tar -xzf arkiv -C mapp sökväg", "packa upp en sak i en mapp"),
               ("awk -F, '{s+=$3} END{print s}' fil", "summera kolumn 3 i en csv-fil"), ("grep -n ord fil", "visa radnummer")],
    "outro": ("GUS: \"Hon kopierade Marias nyckel den 26 september och raderade allt efter sig den 28:e. Anteckningen fanns kvar i backupen, "
              "och den var tydlig. Erik på konkurrent-x betalar. Falk fick 40 000 kronor för ett konsultuppdrag som inte fanns. "
              "Hon var aldrig målet. Hon var ett skäl för oss att titta åt fel håll.\""),
    "missions": [
        {"text": "Läs `hemmappar/sholm/.bash_history`. Sofia kopierade en privat nyckel. Vems nyckel? Svara med användarnamnet.",
         "hints": ["En nyckelfil heter oftast `id_` något. Sök på det.", "Skriv `grep id_ed25519 hemmappar/sholm/.bash_history`. Sökvägen visar vems hemmapp den låg i."],
         "sol": ["grep id_ed25519 hemmappar/sholm/.bash_history", ("svar", "mbergman")], "ans": "mbergman", "xp": 15,
         "after": "`cp /home/mbergman/.ssh/id_ed25519 ~/.cache/k`. Hon kopierade nyckeln och lade den i en dold mapp."},
        {"text": "På vilken rad i `.bash_history` står kommandot som kopierar nyckeln? Svara med radnumret.",
         "hints": ["`grep` kan visa radnummer.", "Skriv `grep -n id_ed25519 hemmappar/sholm/.bash_history`."],
         "sol": ["grep -n id_ed25519 hemmappar/sholm/.bash_history", ("svar", lambda g: g.S["key_line"])], "ans": lambda g: g.S["key_line"], "xp": 10,
         "after": "Läser man raderna runt omkring blir det en berättelse: kopiera, göra privat, logga in, redigera två skript, radera nyckeln, radera anteckningsmappen."},
        {"text": "Nyckeln kunde kopieras eftersom Marias nyckelfil `hemmappar/mbergman/.ssh/id_ed25519` var läsbar för alla. Se efter med `ls -l`, och gör den privat så att bara ägaren kan läsa och skriva.",
         "hints": ["`ls -l` visar rättigheterna. `chmod` ändrar dem.", "Sexhundra betyder läs och skriv för ägaren, ingenting för andra. Skriv `chmod 600` följt av filen."],
         "sol": ["ls -l hemmappar/mbergman/.ssh", "chmod 600 hemmappar/mbergman/.ssh/id_ed25519"],
         "check": lambda g: isfile(g, "hemmappar/mbergman/.ssh/id_ed25519") and (mode(g, "hemmappar/mbergman/.ssh/id_ed25519") & 0o077) == 0, "xp": 20,
         "after": "En privat nyckel som alla kan läsa är i praktiken ett lösenord på en lapp. Nu är den låst."},
        {"text": "Sofia ändrade även `backup_natt.sh`. Jämför `norrsken/jobb/backup_natt.sh` med originalet i `historik/original/`. Hur många rader har lagts till?",
         "hints": ["`diff` jämför. Räkna raderna som börjar med `>`.", "Skriv `diff historik/original/backup_natt.sh norrsken/jobb/backup_natt.sh | grep -c \"^>\"`."],
         "sol": ["diff historik/original/backup_natt.sh norrsken/jobb/backup_natt.sh | grep -c \"^>\"", ("svar", lambda g: g.S["diff_added"])], "ans": lambda g: g.S["diff_added"], "xp": 15,
         "after": "Två rader, den ena en kommentar som ser ut som underhåll. Den andra tömmer arkivet."},
        {"text": "Läs diffen. Backuperna blir tomma om dagens datum är senare än ett visst datum. Vilket? Svara i formen ÅÅÅÅ-MM-DD.",
         "hints": ["Titta på raderna med `>` i diffen.", "Skriv `diff historik/original/backup_natt.sh norrsken/jobb/backup_natt.sh`. Datumet står i raden med `[[ ... ]]`."],
         "sol": ["diff historik/original/backup_natt.sh norrsken/jobb/backup_natt.sh", ("svar", "2026-09-28")], "ans": "2026-09-28", "xp": 15,
         "after": "Den 28 september, klockan 23.53. Backupen tog sin sista hela kopia och nästa natt var arkivet tomt. Ingen kontrollerade."},
        {"text": "Sofia raderade mappen `.anteckningar` ur sin hemmapp, men den finns kvar i backupen `backup/natt_2026-09-28.tar.gz`. Skapa mappen `bevis` och packa upp hela `.anteckningar` dit.",
         "hints": ["`tar -tzf` listar arkivets innehåll. Filtrera med `grep anteckningar` för att se sökvägen.", "`tar -xzf arkiv -C bevis sökväg` packar upp en mapp dit. Sökvägen börjar med `hemmappar/`.",
                   "`mkdir bevis` och sedan `tar -xzf backup/natt_2026-09-28.tar.gz -C bevis hemmappar/sholm/.anteckningar`."],
         "sol": ["mkdir bevis", "tar -tzf backup/natt_2026-09-28.tar.gz | grep anteckningar",
                 "tar -xzf backup/natt_2026-09-28.tar.gz -C bevis hemmappar/sholm/.anteckningar"],
         "check": _restored_both, "xp": 35,
         "after": "En backup är ett bevis. Det som raderades efteråt finns kvar i den."},
        {"text": "Läs `plan.txt`. Kontakten på konkurrentföretaget har ett förnamn. Vilket?",
         "hints": ["Filen ligger under `bevis`, i samma sökväg som i arkivet.", "Skriv `cat bevis/hemmappar/sholm/.anteckningar/plan.txt`."],
         "sol": ["cat bevis/hemmappar/sholm/.anteckningar/plan.txt", ("svar", "Erik")], "ans": "Erik", "xp": 10,
         "after": "Erik på konkurrent-x. Samma Erik som Falk skickade planen till."},
        {"text": "Läs `betalning.csv` i bevismappen. Hur mycket är Sofia lovad totalt? Summera kolumnen `belopp` för hennes rader.",
         "hints": ["Filtrera rader med `grep sholm`. Summera med `awk`.", "`awk -F, '{s+=$3} END{print s}'` summerar kolumn 3. Skicka de filtrerade raderna dit.",
                   "Skriv `grep sholm bevis/hemmappar/sholm/.anteckningar/betalning.csv | awk -F, '{s+=$3} END{print s}'`."],
         "sol": ["grep sholm bevis/hemmappar/sholm/.anteckningar/betalning.csv | awk -F, '{s+=$3} END{print s}'", ("svar", "250000")], "ans": "250000", "xp": 30,
         "after": "250 000 kronor, i tre delar. Det motsvarar ungefär vad ett halvt års lön kostar på Fyrtornet."},
        {"text": "Hur mycket lovades Lena Falk? Svara med beloppet i kronor.",
         "hints": ["Samma fil. Sök på hennes användarnamn.", "Skriv `grep lfalk bevis/hemmappar/sholm/.anteckningar/betalning.csv`."],
         "sol": ["grep lfalk bevis/hemmappar/sholm/.anteckningar/betalning.csv", ("svar", "40000")], "ans": ["40000", "40 000"], "xp": 10,
         "after": "40 000 kronor för att göra det hon fick höra var ett konsultuppdrag. Hon behövde aldrig veta mer. Det var hela poängen."},
    ],
}

# ------------------------------------------------------------ fall 5: klockan tickar

def build15(g):
    r = random.Random(15 * 1000003 + g.seed)
    fallbok(g, [
        "Sofia Holm (sholm) använde Marias konto (mbergman) från sin bärbara LT-0417 och la in sabotage i rensa_gamla_data.sh och backup_natt.sh.",
        "Hon kopierade Marias privata nyckel och raderade sina spår. Anteckningen fanns i backupen.",
        "Konkurrent-x betalar. Lena Falk lurades med ett falskt konsultuppdrag, som skydd.",
        "Sabotagekoden kan ha kopierats till fler skript. Den dolda strängen börjar på " + BLOB_KEY + " och kan sökas i norrsken och hemmappar.",
        "Senaste hela backupen är natt_2026-09-28. Ändringar därefter finns bara i binlog.",
    ])
    rows = orders()
    base = rows[:BASE_ROWS]
    ins = rows[BASE_ROWS:]
    W(g, "norrsken/data/kunder.csv", customers_csv())
    targz(g, "backup/natt_2026-09-28.tar.gz", {"preorders.csv": CSV_HEAD + csv_rows(base), "kunder.csv": customers_csv()}, "2026-09-28")
    for d in days("2026-09-29", "2026-10-15"):
        empty_file(g, "backup/natt_%s.tar.gz" % d, d)
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
                ev.append((ts, "UPDATE kunder %d" % r.randint(1, 60)))
            elif k < 0.85:
                ev.append((ts, "INSERT ordrar %d,%d" % (r.randint(10000, 99999), r.randint(1, 60))))
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
    g.S["expected"] = CSV_HEAD + csv_rows(rows)
    g.S["base_expected"] = CSV_HEAD + csv_rows(base)

    # sabotagekopior
    def infect(name, body):
        return "#!/bin/bash\n# " + name + "\n" + body + '_k="' + BLOB + '"\n_c="$(printf \'%s\' "$_k" | base64 -d)"\neval "$_c"\n'
    W(g, "norrsken/jobb/statistik.sh", infect("statistik.sh", "echo statistik\n"), mode=0o755)
    W(g, "norrsken/jobb/mailko_tomning.sh", infect("mailko_tomning.sh", "echo mailkön\n"), mode=0o755)
    W(g, "norrsken/konfig/profil.d/zz_kompat.sh", infect("zz_kompat.sh", ""), mode=0o644)
    W(g, "hemmappar/mbergman/.profile", infect(".profile", "export EDITOR=vim\n"), mode=0o644)
    W(g, "norrsken/jobb/hamta_cert.sh",
      '#!/bin/bash\n# hämtar certifikat och avkodar det\ncert="LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0t"\necho "$cert" | base64 -d > "$HOME/norrsken/konfig/cert.pem"\n', mode=0o755)
    W(g, "norrsken/jobb/rotera_loggar.sh", "#!/bin/bash\n# rotera_loggar.sh\necho rotera\n", mode=0o755)
    W(g, "norrsken/jobb/cache_tomning.sh", "#!/bin/bash\n# cache_tomning.sh\necho cache\n", mode=0o755)
    for u in ("tnilsson", "jekberg", "pwallin", "sholm"):
        W(g, "hemmappar/%s/.profile" % u if u != "sholm" else "hemmappar/sholm/.profile", "export EDITOR=vim\n")
    g.S["infected"] = "4"


def _no_blob_left(g):
    for top in ("norrsken", "hemmappar"):
        base = g.P(top)
        for d, _, fs in os.walk(base):
            for f in fs:
                try:
                    with open(os.path.join(d, f), encoding="utf-8", errors="ignore") as h:
                        if BLOB in h.read():
                            return False
                except OSError:
                    pass
    return True


INFECTED = {"statistik.sh", "mailko_tomning.sh", "zz_kompat.sh", ".profile"}


def _quarantine5(g):
    k = g.P("karantan")
    if not os.path.isdir(k):
        return False
    return INFECTED <= set(os.listdir(k)) and _no_blob_left(g)


def _restore_base(g):
    return read(g, "norrsken/data/preorders.csv") == g.S["base_expected"]


def _restore_all(g):
    return read(g, "norrsken/data/preorders.csv") == g.S["expected"]


def _incident(g):
    t = read(g, "incident.txt").casefold()
    return (all(x in t for x in ("sholm", "mbergman", "lfalk", "rensa_gamla_data", "konkurrent-x"))
            and isfile(g, "incident.txt") and (mode(g, "incident.txt") & 0o077) == 0)


L15 = {
    "case": True,
    "title": "Klockan tickar",
    "story": ("Torsdag 2026-10-15, kl. 21.40. Du vet vem, hur och varför. Lanseringen är på måndag och det finns tre saker kvar.\n\n"
              "Det första är att städa efter Sofia. Hon hade tid att kopiera sabotagekoden till fler skript innan hon gick. "
              "Det andra är att få tillbaka de 1 847 kunderna. Backupen är gammal, men det finns en logg över allt som hänt sedan dess. "
              "Det tredje är rapporten.\n\n"
              "\"Det här är den svåra delen\", säger GUS. \"Att hitta någon skyldig är det lätta. Att laga det så att ingen märker att det brustit är svårare.\""),
    "learn": ("Inga nya kommandon. Det är samma verktyg, men mer av dem i samma uppdrag.\n\n"
              "- En `for`-slinga går igenom en lista: `for f in $(kommando); do mv \"$f\" mapp/; done`.\n"
              "- `sed 's/.*ord //'` tar bort allt fram till och med ordet på varje rad.\n"
              "- `>>` lägger till sist i en fil. `>` skriver över den.\n"
              "- `binlog/` innehåller en fil per dag med varje ändring i databasen, i tidsordning."),
    "build": build15,
    "cheats": [("for f in $(cmd); do ...; done", "gör något för varje träff"), ("sed 's/.*ord //'", "ta bort allt före ett ord"),
               ("grep -h", "visa träffar utan filnamn"), ("grep -rl ord mapp", "lista filer som innehåller ordet")],
    "outro": ("GUS: \"Förbeställningarna är tillbaka, alla 1 847. Sabotagekoden ligger i karantän på fyra ställen. Rapporten ligger hos Johan.\""),
    "missions": [
        {"text": "Sabotagekoden kan ha kopierats till fler filer. Dess dolda sträng börjar på `" + BLOB_KEY + "` (se `fallbok.txt`). Hur många filer under `norrsken` och `hemmappar` innehåller den?",
         "hints": ["`grep -r` söker i en hel mapp och `-l` listar bara filnamnen.", "Sök i båda mapparna på en gång. Lägg till `| wc -l` för att räkna.",
                   "Skriv `grep -rl " + BLOB_KEY + " norrsken hemmappar | wc -l`."],
         "sol": ["grep -rl " + BLOB_KEY + " norrsken hemmappar | wc -l", ("svar", "4")], "ans": "4", "xp": 20,
         "after": "Fyra kopior. En av dem ligger i Marias `.profile`, som körs varje gång hon loggar in."},
        {"text": "Flytta de fyra filerna till en ny mapp `karantan` i din hemmapp så att sabotagekoden inte finns kvar på fler ställen.",
         "hints": ["`mkdir karantan` först. Sedan behöver du flytta flera filer på en gång.", "En `for`-slinga kan gå igenom resultatet av `grep -rl`.",
                   "`for f in $(grep -rl " + BLOB_KEY + " norrsken hemmappar); do mv \"$f\" karantan/; done`."],
         "sol": ["mkdir karantan", "for f in $(grep -rl " + BLOB_KEY + " norrsken hemmappar); do mv \"$f\" karantan/; done"], "check": _quarantine5, "xp": 35,
         "after": "Fyra filer på fyra ställen. Ett skript som körs varje natt, ett som körs vid inloggning och två som bara ligger och väntar."},
        {"text": "Börja återställningen. Packa upp `preorders.csv` ur backupen `backup/natt_2026-09-28.tar.gz` till `norrsken/data`.",
         "hints": ["`tar -xzf` packar upp. Flaggan `-C` väljer var. Ange filnamnet sist.", "Skriv `tar -xzf backup/natt_2026-09-28.tar.gz -C norrsken/data preorders.csv`."],
         "sol": ["tar -xzf backup/natt_2026-09-28.tar.gz -C norrsken/data preorders.csv"], "check": _restore_base, "xp": 20,
         "after": "1 240 förbeställningar är tillbaka. Det fattas 607."},
        {"text": "Alla ändringar sedan backupen finns i `binlog/`, en fil per dag. Nya förbeställningar står som rader med `INSERT preorders`. Hur många sådana rader finns i alla filer tillsammans?",
         "hints": ["`grep -h` söker utan att skriva filnamnet framför varje rad. Glob `*` tar alla filer.", "Skriv `grep -h \"INSERT preorders\" binlog/*.sql | wc -l`."],
         "sol": ["grep -h \"INSERT preorders\" binlog/*.sql | wc -l", ("svar", lambda g: g.S["ins"])], "ans": lambda g: g.S["ins"], "xp": 20,
         "after": "607 nya förbeställningar under 17 dygn. Den siffran plus 1 240 blir 1 847."},
        {"text": "Loggen `binlog/2026-10-15.sql` innehåller även raden som raderade alla förbeställningar. Den får inte köras om. På vilken rad står den? Svara med radnumret.",
         "hints": ["Sök efter `DELETE preorders` och visa radnummer.", "Skriv `grep -n \"DELETE preorders\" binlog/2026-10-15.sql`."],
         "sol": ["grep -n \"DELETE preorders\" binlog/2026-10-15.sql", ("svar", lambda g: g.S["del_line"])], "ans": lambda g: g.S["del_line"], "xp": 20,
         "after": "Bara `INSERT preorders` ska in i filen. Allt annat, inklusive raden med `DELETE`, hålls utanför."},
        {"text": "Bygg färdigt `norrsken/data/preorders.csv`. Lägg till alla `INSERT preorders`-rader från `binlog/` sist i filen, utan datum, tid och ordet INSERT. Filen ska bara ha id, epost, produkt och antal, precis som raderna som redan finns.",
         "hints": ["`grep -h` plockar raderna. `sed` kan ta bort allt före `INSERT preorders `. `>>` lägger till sist.", "Ordningen på filerna spelar roll. `binlog/*.sql` sorteras redan efter datum.",
                   "`grep -h \"INSERT preorders\" binlog/*.sql | sed 's/.*INSERT preorders //' >> norrsken/data/preorders.csv`."],
         "sol": ["grep -h \"INSERT preorders\" binlog/*.sql | sed 's/.*INSERT preorders //' >> norrsken/data/preorders.csv"], "check": _restore_all, "xp": 40,
         "after": "Alla förbeställningar i rätt ordning. Du har kört samma logg som databasen skulle ha kört, med skillnaden att du hoppade över raderingen."},
        {"text": "Hur många förbeställningar innehåller den återställda filen? Rubrikraden ska inte räknas med.",
         "hints": ["`wc -l` räknar rader, inklusive rubriken.", "Skriv `wc -l norrsken/data/preorders.csv` och dra bort ett."],
         "sol": ["wc -l norrsken/data/preorders.csv", ("svar", str(TOTAL_ROWS))], "ans": [str(TOTAL_ROWS), "1 847"], "xp": 15,
         "after": "1 847, samma siffra som databasen raderade. Ingen kund har försvunnit."},
        {"text": "Skriv rapporten. Skapa `incident.txt` som nämner den skyldiga (användarnamn), kontot som missbrukades, skriptet som sabotagekoden låg i, företaget som betalade och den som användes som skydd. Gör filen läsbar bara för dig.",
         "hints": ["`echo` och `>` skapar filen. `chmod 600` gör den privat.", "Ta med `sholm`, `mbergman`, `rensa_gamla_data`, `konkurrent-x` och `lfalk`.",
                   "Skriv `echo \"sholm använde kontot mbergman för att lägga sabotage i rensa_gamla_data.sh. Konkurrent-x betalade. lfalk användes som skydd.\" > incident.txt` och sedan `chmod 600 incident.txt`."],
         "sol": ["echo \"sholm använde kontot mbergman för att lägga sabotage i rensa_gamla_data.sh. Konkurrent-x betalade. lfalk användes som skydd.\" > incident.txt",
                 "chmod 600 incident.txt"], "check": _incident, "xp": 40,
         "after": "En rapport som pekar ut vem, hur och varför, och som bara du kan läsa. Nu kan Johan ta den vidare."},
    ],
}

CASES = [L11, L12, L13, L14, L15]

EPILOGUE = (
    "GUS: \"Sofia Holm hämtades på fredag morgon. Erik på konkurrent-x fick ett brev från Fyrtornets advokat. "
    "Lena Falk har haft ett långt samtal med HR och har fått veta hur mycket hon egentligen var värd för dem. "
    "Norrsken lanserades på måndag med alla 1 847 förbeställningar på plats.\"\n\n"
    "\"Du började med att lära dig vad en mapp är. Du slutade med att avväpna en tidsinställd bomb, "
    "spåra ett hackat konto och återställa en databas ur en logg. Det gjorde du utan att klicka en enda gång.\"\n\n"
    "GUS lägger till: \"Jag har inte fler ärenden till dig. Men det kommer fler. Det gör det alltid.\""
)
