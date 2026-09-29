#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Terminalspelet. Lär dig terminalen genom att köra riktiga kommandon på riktiga filer.

Spelet kör dina kommandon i en avspärrad mapp (~/.terminalspelet/hem).
Innehållet i nivåerna ligger i levels.py.
"""
import atexit
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time

try:
    import readline
except ImportError:  # pragma: no cover
    readline = None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import levels as levels_sv  # noqa: E402

levels = levels_sv
LANG = "sv"
BASE = ROOT = STATE = SAVE = None


def set_lang(code):
    """Väljer språk (sv eller en) och laddar rätt nivåmodul."""
    global LANG, levels
    LANG = "en" if code == "en" else "sv"
    if LANG == "en":
        import levels_en
        levels = levels_en
    else:
        levels = levels_sv


def L(sv, en):
    return en if LANG == "en" else sv


def init_paths(base):
    global BASE, ROOT, STATE, SAVE
    BASE = base
    os.makedirs(os.path.join(base, "hem"), exist_ok=True)
    os.makedirs(os.path.join(base, "skal"), exist_ok=True)
    ROOT = os.path.realpath(os.path.join(base, "hem"))
    STATE = os.path.realpath(os.path.join(base, "skal"))
    SAVE = os.path.join(base, "save.json")


# ---------------------------------------------------------------- utseende

COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ


def col(code, s):
    return "\033[%sm%s\033[0m" % (code, s) if COLOR else s


def bold(s): return col("1", s)
def dim(s): return col("2", s)
def red(s): return col("31", s)
def green(s): return col("32", s)
def yellow(s): return col("33", s)
def mag(s): return col("35", s)
def cyan(s): return col("36", s)


def width():
    return max(44, min(shutil.get_terminal_size((80, 24)).columns - 4, 76))


def inline(s):
    return re.sub(r"`([^`]+)`", lambda m: cyan(m.group(1)), s)


def say(text, indent=2):
    pad = " " * indent
    for para in text.split("\n"):
        if not para.strip():
            print()
        elif para.startswith("$ "):
            print(pad + "  " + cyan(para))
        elif para.startswith("- "):
            print(inline(textwrap.fill(para[2:], width=width(), initial_indent=pad + "• ",
                                       subsequent_indent=pad + "  ")))
        else:
            print(inline(textwrap.fill(para, width=width(), initial_indent=pad,
                                       subsequent_indent=pad)))


def gus(text):
    label = mag("GUS ▸ ")
    lines = textwrap.wrap(text, width=width() - 8)
    for i, ln in enumerate(lines):
        print("  " + (label if i == 0 else "      ") + inline(ln))


def rule(title="", char="─"):
    w = width()
    if title:
        t = " %s " % title
        print(cyan("  " + char * 2 + t + char * max(2, w - len(t) - 2)))
    else:
        print(cyan("  " + char * w))


def clear():
    if COLOR:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


BANNER = r"""
  _____ _____ ____  __  __ ___ _   _   _    _     ____  ____  _____ _     _____ _____
 |_   _| ____|  _ \|  \/  |_ _| \ | | / \  | |   / ___||  _ \| ____| |   | ____|_   _|
   | | |  _| | |_) | |\/| || ||  \| |/ _ \ | |   \___ \| |_) |  _| | |   |  _|   | |
   | | | |___|  _ <| |  | || || |\  / ___ \| |___ ___) |  __/| |___| |___| |___  | |
   |_| |_____|_| \_\_|  |_|___|_| \_/_/   \_\_____|____/|_|   |_____|_____|_____| |_|
"""

BANNER_SMALL = "  T E R M I N A L S P E L E T"

RANKS = {
    "sv": ["Praktikant", "Mappvandrare", "Filsnokare", "Rörmokare", "Rättighetsvakt",
           "Processjägare", "Skriptare", "Systemtrollkarl", "Terminalmästare"],
    "en": ["Intern", "Folder Walker", "File Sniffer", "Pipe Fitter", "Permission Keeper",
           "Process Hunter", "Scripter", "System Wizard", "Terminal Master"],
}


def rank_names():
    return RANKS[LANG]


RANK_PCT = [0, 6, 16, 28, 42, 57, 72, 88, 100]


def max_xp():
    return sum(m["xp"] for lv in levels.LEVELS for m in lv["missions"])


def rank_for(xp):
    top = max_xp()
    idx = 0
    for i, pct in enumerate(RANK_PCT):
        if xp >= top * pct / 100.0:
            idx = i
    return idx, rank_names()[idx]


# ---------------------------------------------------------------- säkerhetsvakt

BLOCKED = {"sudo", "su", "dd", "mkfs", "shutdown", "reboot", "halt", "killall", "pkill",
           "launchctl", "diskutil", "chown", "osascript"}
ALLOWED_ABS = ["/dev/null", "/bin", "/usr/bin", "/usr/local/bin"]
KEEP_CMDPOS = {"do", "then", "else", "!", "time", "elif"}
PATHLIKE = re.compile(r"^[\w./~+@%,:=*?\[\]{}-]+$")


def tokens(cmd):
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    return list(lex)


def within(p):
    return p == ROOT or p.startswith(ROOT + os.sep)


TIPS = [
    ("command not found",
     "Kommandot finns inte. Titta efter stavfel, och kom ihåg att terminalen skiljer på stora och små bokstäver.",
     "That command does not exist. Check the spelling, and remember the terminal cares about upper and lower case."),
    ("No such file or directory",
     "Filen eller mappen finns inte där du står. Kolla med `pwd` var du är och `ls` vad som finns.",
     "That file or folder is not where you are standing. Check with `pwd` where you are and `ls` what is here."),
    ("Permission denied",
     "Du saknar rättighet att göra det. `ls -l` visar vem som får göra vad.",
     "You lack permission to do that. `ls -l` shows who may do what."),
    ("Is a directory",
     "Det där är en mapp, inte en fil. Använd `ls` eller `cd`.",
     "That is a folder, not a file. Use `ls` or `cd`."),
    ("Not a directory",
     "Det där är en fil, inte en mapp.",
     "That is a file, not a folder."),
    ("File exists",
     "Det finns redan något med det namnet.",
     "Something with that name already exists."),
    ("usage:",
     "Kommandot saknar något. Lägg till det som usage-raden ovanför visar.",
     "The command is missing something. Add what the usage line above shows."),
]


class Shell:
    def __init__(self):
        self.cwd = ROOT
        self.prev = ROOT
        self.name = "agent"

    def path_violation(self, t):
        s = t
        m = re.match(r"^-{1,2}[\w-]+=(.*)$", s)
        if m:
            s = m.group(1)
        if not s or s.startswith("-"):
            return None
        if "$" in s or "`" in s:
            return None
        if s.startswith("~"):
            if s == "~" or s.startswith("~/"):
                s = ROOT + s[1:]
            else:
                return t
        if not (s == ".." or "/" in s):
            return None
        if not PATHLIKE.match(s):
            return None
        absp = s if s.startswith("/") else os.path.join(self.cwd, s)
        p = os.path.normpath(absp)
        if within(p):
            return None
        for ok in ALLOWED_ABS:
            if p == ok or p.startswith(ok + "/"):
                return None
        if s.startswith("/") and not os.path.exists(p):
            parent = os.path.dirname(p)
            if parent == "/" or not os.path.exists(parent):
                return None  # ser ut som ett mönster, till exempel /ERROR/
        return t

    def guard(self, cmd, allowed_pids):
        try:
            toks = tokens(cmd)
        except ValueError:
            return None
        cmdpos = True
        current = ""
        for t in toks:
            if set(t) <= set(";|&()<>"):
                if not set(t) <= set("<>"):
                    cmdpos = True
                continue
            if cmdpos:
                if t in KEEP_CMDPOS:
                    continue
                if re.match(r"^\w+=", t):
                    continue
                current = os.path.basename(t)
                if current in BLOCKED:
                    return L("Det kommandot rör systemet utanför övningen. Det håller jag dig ifrån.",
                             "That command touches the system outside the exercise. I am keeping you away from it.")
                cmdpos = False
            elif current == "kill" and t.isdigit() and int(t) not in allowed_pids:
                return L("Den processen är inte din att döda. Ta bara den som spelet pekar ut.",
                             "That process is not yours to kill. Only take the one the game points out.")
            v = self.path_violation(t)
            if v:
                if v == "..":
                    return L("Du står redan i toppen av övningsområdet. Högre upp finns bara din riktiga dator.",
                                 "You are already at the top of the exercise area. Above this is only your real computer.")
                return L("Den stigen ligger utanför övningsområdet. Jag släpper inte ut dig.",
                             "That path is outside the exercise area. I am not letting you out.")
        return None

    def run(self, cmd, quiet=False):
        wrap = levels.WRAP
        env = dict(os.environ)
        env.pop("PS1", None)
        env.update({
            "HOME": ROOT, "USER": self.name, "LOGNAME": self.name,
            "LC_ALL": "en_US.UTF-8", "TS_STATE": STATE, "TS_CWD": self.cwd,
            "TS_OLDPWD": self.prev, "TS_CMD": cmd,
        })
        sys.stdout.flush()
        proc = subprocess.Popen(["/bin/bash", "-c", wrap], env=env,
                                stdout=subprocess.PIPE if quiet else None,
                                stderr=subprocess.PIPE)
        try:
            out, err = proc.communicate()
        except KeyboardInterrupt:
            proc.terminate()
            out, err = proc.communicate()
            print()
        before = self.cwd
        try:
            with open(os.path.join(STATE, "cwd")) as f:
                new = f.read().strip()
            with open(os.path.join(STATE, "oldpwd")) as f:
                old = f.read().strip()
        except OSError:
            new, old = self.cwd, self.prev
        err_text = err.decode("utf-8", "replace") if err else ""
        note = None
        if not within(new):
            new = ROOT
            note = L("Du hamnade utanför övningsområdet, så jag flyttade hem dig.",
                     "You ended up outside the exercise area, so I moved you home.")
        if new != before:
            self.prev = old if within(old) else before
        self.cwd = new
        return {"cmd": cmd, "ec": proc.returncode, "before": before, "after": new,
                "err": err_text, "out": (out or b"").decode("utf-8", "replace"), "note": note}


# ---------------------------------------------------------------- spelet

def norm(s):
    return re.sub(r"[\s\"'`]", "", str(s)).casefold()


class Game:
    def __init__(self, interactive=True, quiet=False):
        self.interactive = interactive
        self.quiet = quiet
        self.sh = Shell()
        self.root = ROOT
        self.state = STATE
        self.S = {}
        self.procs = []
        self.mh = []
        self.lh = []
        self.last = None
        self.hints = 0
        self.sol_shown = False
        self.level_xp = 0
        self.data = {"name": None, "level": 0, "xp": 0, "done": 0}
        self.load()
        atexit.register(self.kill_procs)

    # hjälpare som nivåerna använder
    def P(self, rel):
        return os.path.join(ROOT, rel)

    @property
    def cwd(self):
        return self.sh.cwd

    @property
    def allowed_pids(self):
        return set(p.pid for p in self.procs)

    # sparning
    def load(self):
        try:
            with open(SAVE) as f:
                self.data.update(json.load(f))
        except (OSError, ValueError):
            pass

    def save(self):
        if not self.interactive:
            return
        with open(SAVE, "w") as f:
            json.dump(self.data, f)

    @property
    def name(self):
        return self.data.get("name") or "agent"

    # världen
    def kill_procs(self):
        for p in self.procs:
            try:
                if p.poll() is None:
                    p.kill()
                    p.wait()
            except OSError:
                pass
        self.procs = []

    def wipe(self):
        self.kill_procs()
        for n in os.listdir(ROOT):
            p = os.path.join(ROOT, n)
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p, ignore_errors=True)
            else:
                try:
                    os.remove(p)
                except OSError:
                    pass
        for n in os.listdir(STATE):
            try:
                os.remove(os.path.join(STATE, n))
            except OSError:
                pass

    def start_level(self, idx):
        lv = levels.LEVELS[idx]
        self.wipe()
        self.S = {}
        self.sh = Shell()
        self.sh.name = self.name
        lv["build"](self)
        self.sh.cwd = os.path.join(ROOT, lv.get("start", "")).rstrip("/")
        self.sh.prev = ROOT
        self.lh = []
        self.mh = []
        self.last = None
        self.level_xp = 0

    # körning av kommandon
    def execute(self, cmd):
        why = self.sh.guard(cmd, self.allowed_pids)
        if why:
            if not self.quiet:
                print()
                gus(why)
            return None
        entry = self.sh.run(cmd, quiet=self.quiet)
        for p in self.procs:
            p.poll()
        self.last = entry
        self.mh.append(entry)
        self.lh.append(entry)
        if entry["err"] and not self.quiet:
            sys.stderr.write(red(entry["err"]))
            if not entry["err"].endswith("\n"):
                sys.stderr.write("\n")
            sys.stderr.flush()
            for needle, tip_sv, tip_en in TIPS:
                if needle in entry["err"]:
                    print(dim(inline("  ↳ " + L(tip_sv, tip_en))))
                    break
        if entry["note"] and not self.quiet:
            gus(entry["note"])
        return entry

    def expand_ps1(self, ps1):
        c = self.sh.cwd
        w = "~" + c[len(ROOT):] if within(c) else c
        base = "~" if c == ROOT else os.path.basename(c)
        table = {"u": self.name, "h": "nod7", "w": w, "W": base, "$": "$", "n": "\n",
                 "t": time.strftime("%H:%M:%S"), "A": time.strftime("%H:%M"), "e": "\033",
                 "033": "\033", "x1b": "\033", "[": "\001", "]": "\002", "a": "", "\\": "\\"}
        out = re.sub(r"\\(033|x1b|.)", lambda m: table.get(m.group(1), "\\" + m.group(1)), ps1)
        if not COLOR:
            out = re.sub(r"\033\[[0-9;]*m", "", out)
        return out

    def prompt(self):
        try:
            with open(os.path.join(STATE, "ps1"), encoding="utf-8") as f:
                ps1 = f.read()
        except OSError:
            ps1 = ""
        if ps1.strip():
            return self.expand_ps1(ps1)
        home = ROOT
        c = self.sh.cwd
        shown = "~" + c[len(home):] if within(c) else c
        who = "%s@nod7" % self.name
        if COLOR:
            return "\001\033[32m\002%s\001\033[0m\002 \001\033[36m\002%s\001\033[0m\002 $ " % (who, shown)
        return "%s %s $ " % (who, shown)

    def setup_readline(self):
        if not readline:
            return
        readline.set_completer_delims(" \t\n;|&<>()")
        if "libedit" in (readline.__doc__ or ""):
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")
        matches = []

        def completer(text, state):
            if state == 0:
                matches[:] = []
                t = text
                if t.startswith("~"):
                    t = ROOT + t[1:]
                d, base = os.path.split(t)
                folder = d if os.path.isabs(d) else os.path.join(self.sh.cwd, d)
                try:
                    names = os.listdir(folder or self.sh.cwd)
                except OSError:
                    names = []
                shown_dir = os.path.split(text)[0]
                for n in sorted(names):
                    if n.startswith(base) and (base or not n.startswith(".")):
                        full = os.path.join(folder, n)
                        pre = (shown_dir + "/") if shown_dir else ""
                        if text.startswith("/") and shown_dir == "/":
                            pre = "/"
                        matches.append(pre + n + ("/" if os.path.isdir(full) else " "))
            return matches[state] if state < len(matches) else None

        readline.set_completer(completer)

    # skärmar
    def wait(self):
        if self.interactive:
            try:
                input(dim(L("\n  [Enter för att fortsätta] ", "\n  [Press Enter to continue] ")))
            except EOFError:
                pass
            print()

    def choose_language(self):
        print()
        print("  Språk / Language")
        print("    1  Svenska")
        print("    2  English")
        try:
            raw = input("  > ").strip().lower()
        except EOFError:
            raw = ""
        code = "en" if raw in ("2", "en", "english", "e") else "sv"
        self.data["lang"] = code
        set_lang(code)
        self.save()

    def title(self):
        clear()
        print(cyan(BANNER) if width() >= 80 else cyan("\n" + BANNER_SMALL + "\n"))
        if not self.data.get("lang"):
            self.choose_language()
            print()
        say(L("Lär dig terminalen genom att använda den. Riktiga kommandon, riktiga filer, "
              "en gåta som löser sig ju längre du kommer.",
              "Learn the terminal by using it. Real commands, real files, "
              "and a mystery that unravels the further you get."))
        print()
        if not self.data.get("name"):
            say(L("Allt du gör här sker i en egen mapp: `~/.terminalspelet/hem`. Kommandona är på riktigt, "
                  "men spelet stoppar dig innan du kommer utanför mappen. Du kan inte förstöra något.",
                  "Everything you do here happens in its own folder: `~/.terminalspelet/hem`. The commands are real, "
                  "but the game stops you before you leave the folder. You cannot break anything."))
            print()
            try:
                raw = input(L("  Vad ska jag kalla dig, agent? ", "  What should I call you, agent? ")).strip()
            except EOFError:
                raw = ""
            nm = re.sub(r"[^a-z0-9]", "", raw.lower()) or "agent"
            self.data["name"] = nm[:14]
            self.save()
            print()
        else:
            xp = self.data["xp"]
            _, rk = rank_for(xp)
            say(L("Välkommen tillbaka, %s. Rang: %s. %d av %d XP.",
                  "Welcome back, %s. Rank: %s. %d of %d XP.") % (self.name, rk, xp, max_xp()))
            print()

    def intro(self, idx, lv):
        clear()
        n = len(levels.LEVELS)
        rule(L("Nivå %d av %d: %s", "Level %d of %d: %s") % (idx + 1, n, lv["title"]), "═")
        print()
        say(lv["story"])
        print()
        rule(L("Så funkar det", "How it works"), "·")
        print()
        say(lv["learn"])
        print()
        say(L("Skriv `hint` om du kör fast, `mål` för att se uppdraget igen och `hjälp` för alla spelkommandon.",
              "Type `hint` if you get stuck, `goal` to see the mission again and `help` for all game commands."))
        self.wait()

    def show_mission(self, lv, mi, m):
        total = len(lv["missions"])
        bar = "■" * mi + "□" * (total - mi)
        print()
        rule(L("Uppdrag %d av %d  %s", "Mission %d of %d  %s") % (mi + 1, total, bar))
        say(m["text"])
        if m.get("ans") is not None:
            print(dim(L("  Svara med: svar <ditt svar>", "  Answer with: answer <your answer>")))
        print()

    def help(self):
        say(L("Spelkommandon. Skriv dem som vanligt, med eller utan kolon före.",
              "Game commands. Type them as usual, with or without a colon in front."))
        rows = L([("hint", "ett tips, det första är gratis, fler kostar XP"),
                  ("mål", "visa uppdraget igen"),
                  ("svar X", "lämna in ett svar när uppdraget ber om det"),
                  ("lär", "läs nivåns förklaring igen"),
                  ("fusklapp", "alla kommandon du lärt dig hittills"),
                  ("poäng", "din rang och dina XP"),
                  ("lösning", "visa hur man gör (uppdraget ger då 0 XP)"),
                  ("hoppa", "spelet gör uppdraget åt dig (0 XP)"),
                  ("språk", "byt mellan svenska och engelska (nivån byggs om)"),
                  (":reset", "bygg om nivån och börja om"),
                  ("sluta", "avsluta, nivån börjar om nästa gång")],
                 [("hint", "a tip, the first is free, more cost XP"),
                  ("goal", "show the mission again"),
                  ("answer X", "hand in an answer when the mission asks for one"),
                  ("learn", "read the level explanation again"),
                  ("cheatsheet", "all commands you have learned so far"),
                  ("score", "your rank and XP"),
                  ("solution", "show how it is done (the mission then gives 0 XP)"),
                  ("skip", "the game does the mission for you (0 XP)"),
                  ("lang", "switch between Swedish and English (the level is rebuilt)"),
                  (":reset", "rebuild the level and start over"),
                  ("quit", "leave, the level restarts next time")])
        for a, b in rows:
            print("  " + cyan(a.ljust(12)) + b)
        print()
        say(L("Allt annat du skriver körs som ett riktigt kommando. Piltangenterna bläddrar i tidigare kommandon "
              "och Tab skriver klart filnamn.",
              "Anything else you type runs as a real command. The arrow keys scroll through earlier commands "
              "and Tab completes file names."))

    def cheats_upto(self, idx):
        rows = []
        for lv in levels.LEVELS[:idx]:
            rows.extend(lv["cheats"])
        return rows

    def show_cheats(self, idx_done):
        rows = self.cheats_upto(idx_done)
        if not rows:
            say(L("Inget här än. Klara första nivån först.", "Nothing here yet. Finish the first level first."))
            return
        for a, b in rows:
            print("  " + cyan(a.ljust(30)) + b)

    def write_cheatsheet(self, idx_done):
        rows = self.cheats_upto(idx_done)
        path = os.path.join(BASE, L("fusklapp.txt", "cheatsheet.txt"))
        with open(path, "w", encoding="utf-8") as f:
            f.write(L("FUSKLAPP", "CHEAT SHEET") + "\n\n")
            for a, b in rows:
                f.write("%-32s %s\n" % (a, b))
        return path

    # uppdragsloop
    def add_xp(self, n):
        before, _ = rank_for(self.data["xp"] + self.level_xp)
        self.level_xp += n
        after, name = rank_for(self.data["xp"] + self.level_xp)
        return name if after > before else None

    def complete(self, m, skipped=False):
        xp = 0 if (skipped or self.sol_shown) else round(m["xp"] * max(0.25, 1 - 0.25 * max(0, self.hints - 1)))
        up = self.add_xp(xp)
        print()
        head = green(L("  ✔ Klart", "  ✔ Done")) + (dim("  +%d XP" % xp) if xp else dim("  0 XP"))
        print(head)
        say(m["after"], indent=4)
        if up:
            print()
            print("  " + yellow(L("▲ Ny rang: %s", "▲ New rank: %s") % up))

    def answer_ok(self, m, given):
        exp = m["ans"](self) if callable(m["ans"]) else m["ans"]
        exp = exp if isinstance(exp, (list, tuple)) else [exp]
        g = norm(given)
        opts = set(norm(e) for e in exp)
        opts |= set(norm(os.path.basename(str(e))) for e in exp)
        return g in opts or norm(os.path.basename(given.strip())) in opts

    def sol_text(self, m):
        out = []
        for st in m["sol"]:
            if isinstance(st, tuple):
                v = st[1](self) if callable(st[1]) else st[1]
                out.append(L("svar %s", "answer %s") % v)
            else:
                out.append(st)
        return out

    def read_line(self):
        return input(self.prompt())

    ALIASES = {"hjalp": "hjälp", "help": "hjälp", "?": "hjälp", "mal": "mål", "goal": "mål",
               "lar": "lär", "learn": "lär", "answer": "svar", "losning": "lösning", "solution": "lösning",
               "skip": "hoppa", "fusk": "fusklapp", "cheatsheet": "fusklapp", "cheats": "fusklapp",
               "poang": "poäng", "xp": "poäng", "score": "poäng", "exit": "sluta", "quit": "sluta",
               "avsluta": "sluta", "språk": "lang", "sprak": "lang", "language": "lang"}
    COMMANDS = {"hint", "hjälp", "mål", "lär", "svar", "lösning", "hoppa", "fusklapp", "poäng",
                "sluta", "reset", "lang"}

    def game_cmd(self, word, arg, lv, mi, m, idx):
        word = self.ALIASES.get(word, word)
        if word == "hjälp":
            self.help()
        elif word == "mål":
            self.show_mission(lv, mi, m)
        elif word == "lär":
            print()
            say(lv["learn"])
        elif word == "hint":
            hs = m["hints"]
            n = min(self.hints, len(hs) - 1)
            print()
            gus(hs[n])
            self.hints += 1
            if n == len(hs) - 1:
                print(dim(L("  Kör det fortfarande fast? `lösning` visar hela kommandot.",
                            "  Still stuck? `solution` shows the whole command.")))
            elif self.hints > 1:
                print(dim(L("  Det här tipset kostar 25 % av uppdragets XP.",
                            "  This tip costs 25% of the mission's XP.")))
        elif word == "svar":
            if m.get("ans") is None:
                print()
                gus(L("Inget svar behövs här. Uppdraget avgörs av vad som händer i terminalen.",
                      "No answer is needed here. The mission is decided by what happens in the terminal."))
            elif not arg.strip():
                say(L("Skriv ditt svar efter ordet, till exempel: svar 42",
                      "Type your answer after the word, for example: answer 42"))
            elif self.answer_ok(m, arg):
                return "done"
            else:
                print()
                gus(L("Nej, inte riktigt. Kolla utskriften en gång till, och svara exakt som den står.",
                      "No, not quite. Check the output once more, and answer exactly as it reads."))
        elif word == "lösning":
            self.sol_shown = True
            print()
            gus(L("Så här gör man. Du får 0 XP för det här uppdraget, men du lär dig ändå.",
                  "This is how it is done. You get 0 XP for this mission, but you still learn."))
            for s_ in self.sol_text(m):
                print("    " + cyan(s_))
        elif word == "hoppa":
            print()
            gus(L("Jag gör det åt dig.", "I will do it for you."))
            for st in m["sol"]:
                if isinstance(st, tuple):
                    v = st[1](self) if callable(st[1]) else st[1]
                    print(dim(L("    (svaret är %s)", "    (the answer is %s)") % v))
                else:
                    print("  " + self.prompt().replace("\001", "").replace("\002", "") + cyan(st))
                    self.execute(st)
            return "skip"
        elif word == "fusklapp":
            print()
            self.show_cheats(idx)
            print(dim(L("\n  (Bara de nivåer du klarat finns med. Nästa fusklapp tänds när du klarar nivån.)",
                        "\n  (Only levels you have finished are included. The next batch unlocks when you finish this level.)")))
        elif word == "poäng":
            xp = self.data["xp"] + self.level_xp
            i, rk = rank_for(xp)
            say(L("Rang: %s. %d av %d XP.", "Rank: %s. %d of %d XP.") % (rk, xp, max_xp()))
            if i + 1 < len(rank_names()):
                need = int(max_xp() * RANK_PCT[i + 1] / 100.0 + 0.999)
                say(L("Nästa rang, %s, ligger på %d XP.", "Next rank, %s, starts at %d XP.") % (rank_names()[i + 1], need))
        elif word == "sluta":
            return "quit"
        elif word == "reset":
            return "reset"
        elif word == "lang":
            a = arg.strip().lower()
            new = a if a in ("sv", "en") else ("sv" if LANG == "en" else "en")
            if new == LANG:
                say(L("Spelet kör redan på svenska.", "The game is already in English."))
            else:
                set_lang(new)
                self.data["lang"] = new
                self.save()
                return "lang"
        else:
            say(L("Det där spelkommandot finns inte. `hjälp` visar listan.",
                  "That game command does not exist. `help` shows the list."))
        return None

    BARE = set(ALIASES) | (COMMANDS - {"reset"})

    def handle(self, line, lv, mi, m, idx):
        s = line.strip()
        if not s:
            return None
        parts = s.lstrip(":").split(None, 1)
        word = parts[0] if parts else ""
        arg = parts[1] if len(parts) > 1 else ""
        if s.startswith(":") or (word in self.BARE and not (word in ("exit", "quit", "xp", "score") and arg)):
            return self.game_cmd(word, arg, lv, mi, m, idx)
        entry = self.execute(s)
        if entry is None:
            return None
        if m.get("check"):
            try:
                if m["check"](self):
                    return "done"
            except Exception:
                return None
        return None

    def play_mission(self, lv, mi, m, idx):
        self.mh = []
        self.hints = 0
        self.sol_shown = False
        self.show_mission(lv, mi, m)
        while True:
            try:
                line = self.read_line()
            except EOFError:
                print()
                return "quit"
            except KeyboardInterrupt:
                print()
                say(L("Avbryt med Ctrl-C funkar i terminalen, men här stänger du spelet med `sluta`.",
                    "Ctrl-C works in the terminal, but here you leave the game with `quit`."))
                continue
            r = self.handle(line, lv, mi, m, idx)
            if r == "done":
                self.complete(m)
                return "done"
            if r == "skip":
                self.complete(m, skipped=True)
                return "done"
            if r in ("quit", "reset", "lang"):
                return r

    def play_level(self, idx):
        while True:
            lv = levels.LEVELS[idx]
            self.start_level(idx)
            self.intro(idx, lv)
            restart = False
            for mi, m in enumerate(lv["missions"]):
                r = self.play_mission(lv, mi, m, idx)
                if r == "quit":
                    return "quit"
                if r in ("reset", "lang"):
                    print()
                    if r == "lang":
                        gus(L("Jag bygger om nivån på svenska. XP du fått i den här nivån nollas.",
                              "I am rebuilding the level in English. XP from this level resets."))
                    else:
                        gus(L("Jag bygger om nivån. XP du fått i den här nivån nollas.",
                              "I am rebuilding the level. XP you earned in this level resets."))
                    restart = True
                    break
            if not restart:
                break
        if lv.get("on_done"):
            try:
                lv["on_done"](self)
            except OSError:
                pass
        self.data["xp"] += self.level_xp
        self.data["level"] = idx + 1
        self.save()
        self.outro(idx, lv)
        return "ok"

    def outro(self, idx, lv):
        print()
        rule(L("Nivå %d klar: %s", "Level %d complete: %s") % (idx + 1, lv["title"]), "═")
        print()
        say(lv["outro"])
        print()
        say(L("Nya kommandon i fusklappen:", "New commands on the cheat sheet:"))
        for a, b in lv["cheats"]:
            print("  " + cyan(a.ljust(30)) + b)
        path = self.write_cheatsheet(idx + 1)
        print()
        _, rk = rank_for(self.data["xp"])
        say(L("Du har %d av %d XP. Rang: %s.", "You have %d of %d XP. Rank: %s.") % (self.data["xp"], max_xp(), rk))
        print(dim(L("  Fusklappen sparas i %s", "  The cheat sheet is saved in %s") % path.replace(os.path.expanduser("~"), "~")))
        self.wait()

    def finale(self):
        clear()
        rule(L("UPPDRAGET KLART", "MISSION COMPLETE"), "═")
        print()
        say(levels.EPILOGUE)
        print()
        i, rk = rank_for(self.data["xp"])
        say(L("Slutresultat: %d av %d XP. Rang: %s.", "Final score: %d of %d XP. Rank: %s.") % (self.data["xp"], max_xp(), rk))
        print()
        say(L("Fusklappen med alla kommandon ligger i `~/.terminalspelet/fusklapp.txt`. "
              "Spara den, eller skriv ut den. Nästa steg är att använda terminalen på riktigt, "
              "till exempel för att hitta något i dina egna mappar.",
              "The cheat sheet with every command is in `~/.terminalspelet/cheatsheet.txt`. "
              "Keep it, or print it. The next step is to use the terminal for real, "
              "for example to find something in your own folders."))
        print()

    def play(self):
        self.setup_readline()
        set_lang(self.data.get("lang") or "sv")
        self.title()
        n = len(levels.LEVELS)
        start = self.data.get("level", 0)
        if start >= n:
            say(L("Du har redan klarat spelet. Vill du köra om det? Skriv ja, annars Enter.", "You have already finished the game. Play again? Type yes, otherwise Enter."))
            try:
                if input("  > ").strip().lower() in ("ja", "j", "yes", "y"):
                    self.data.update({"level": 0, "xp": 0})
                    start = 0
                else:
                    return
            except EOFError:
                return
        for idx in range(start, n):
            if self.play_level(idx) == "quit":
                print()
                say(L("Vi ses. Nivån börjar om nästa gång du startar.", "See you. The level restarts next time you start."))
                return
        self.finale()


def selftest(lang="sv"):
    set_lang(lang)
    tmp = tempfile.mkdtemp(prefix="tspel")
    init_paths(tmp)
    g = Game(interactive=False, quiet=True)
    g.data["name"] = "agent"
    bad = 0
    total = 0
    for li, lv in enumerate(levels.LEVELS):
        g.start_level(li)
        for mi, m in enumerate(lv["missions"]):
            total += 1
            g.mh = []
            label = "N%d.%d" % (li + 1, mi + 1)
            if m.get("check"):
                try:
                    pre = m["check"](g)
                except Exception as e:
                    pre = "fel: %r" % e
                if pre:
                    print("VARNING %s är redan sann innan lösningen: %s" % (label, m["text"][:50]))
            answered = None
            for st in m["sol"]:
                if isinstance(st, tuple):
                    v = st[1](g) if callable(st[1]) else st[1]
                    answered = g.answer_ok(m, str(v)) if m.get("ans") is not None else None
                    wrong = g.answer_ok(m, "fel svar 12345") if m.get("ans") is not None else False
                    if wrong:
                        print("FEL %s accepterar fel svar" % label)
                        bad += 1
                else:
                    e = g.execute(st)
                    if e is None:
                        print("FEL %s blockerades av vakten: %s" % (label, st))
                        bad += 1
            if m.get("check"):
                try:
                    ok = bool(m["check"](g))
                except Exception as e:
                    ok = False
                    print("   undantag:", repr(e))
            else:
                ok = bool(answered)
            print("%s %s %s" % ("ok  " if ok else "FAIL", label, m["text"][:60].replace("\n", " ")))
            if not ok:
                bad += 1
                if g.last:
                    print("     senaste:", g.last["cmd"], "ec", g.last["ec"], g.last["err"][:120])
    g.kill_procs()
    shutil.rmtree(tmp, ignore_errors=True)
    print("\n%d uppdrag, %d fel" % (total, bad))
    return 1 if bad else 0


def main():
    base = os.environ.get("TERMINALSPELET_DIR", os.path.expanduser("~/.terminalspelet"))
    lang = None
    if "--lang" in sys.argv:
        k = sys.argv.index("--lang")
        if k + 1 < len(sys.argv) and sys.argv[k + 1] in ("sv", "en"):
            lang = sys.argv[k + 1]
    if "--selftest" in sys.argv:
        sys.exit(selftest(lang or "sv"))
    init_paths(base)
    if "--nollstall" in sys.argv or "--reset" in sys.argv:
        try:
            os.remove(SAVE)
        except OSError:
            pass
    if not sys.stdin.isatty():
        print("Spelet behöver ett riktigt terminalfönster. Kör ./spela i Terminal.\n"
              "The game needs a real terminal window. Run ./spela in Terminal.")
        sys.exit(1)
    g = Game()
    if lang:
        g.data["lang"] = lang
        g.save()
    try:
        g.play()
    finally:
        g.kill_procs()


if __name__ == "__main__":
    main()
