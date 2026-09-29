# -*- coding: utf-8 -*-
"""English levels for Terminal Game. Same structure as levels.py."""
import os
import random
import re
import shutil
import subprocess
import tarfile
import time
from collections import Counter

from levels import (WRAP, W, D, isdir, isfile, read, mode, state, ran, ranfail,  # noqa: F401
                    lastcmd, walk_files, walk_dirs, hms)


def spawn_spok(g):
    dst = g.P("tools/spok")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    src = "/bin/sleep" if os.path.exists("/bin/sleep") else "/usr/bin/sleep"
    shutil.copy(src, dst)
    os.chmod(dst, 0o755)
    subprocess.run(["codesign", "--force", "-s", "-", dst], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    p = subprocess.Popen([dst, "100000"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    g.procs.append(p)
    g.S["pid"] = p.pid


SENT = [
    "The meeting opened at nine.", "The budget for next quarter was discussed.",
    "The delivery from the supplier is delayed.", "The coffee machine on the third floor will be replaced.",
    "Support reported more calls than usual on Monday.",
    "The chair proposed a follow-up in two weeks.", "Nobody had any comments on the agenda.",
    "The quote was approved without changes.", "The customer survey showed a small improvement.",
    "The next meeting is in conference room Vega.", "The invoices for August are booked.",
    "The server room needs better cooling.", "Hiring a new technician is paused until autumn.",
    "The report goes out on Friday.", "The maintenance window moved to Sunday night.",
]


def prose(r, n=None):
    n = n or r.randint(6, 12)
    return "\n".join(r.choice(SENT) for _ in range(n)) + "\n"


# ------------------------------------------------------------ level 1: the map

def build1(g):
    W(g, "welcome.txt", "Welcome to Fyrtornet AB.\nYour folder is yours. Take it easy.\n")
    W(g, "office/reception/guest_list.txt", "Visitors today: none yet.\n")
    W(g, "office/kitchen/coffee_fund.txt", "Coffee fund: 412 kr.\n")
    W(g, "office/server_room/node7.txt", "node-7 has been up for 214 days.\n")
    D(g, "office/server_room/rack_A")
    D(g, "office/server_room/rack_B")
    D(g, "archive/2019")
    for q in range(1, 5):
        D(g, "archive/2020/q%d" % q)
    W(g, "archive/2020/q4/year_end.txt", "Year-end accounts 2020, fourth quarter.\n")


L1 = {
    "title": "The map",
    "story": ("It is 07:12 on a Monday. You have a badge, a cup of coffee and a window where nothing can be clicked. "
              "Project Norrsken, Fyrtornet's biggest launch, leaked to a competitor overnight. Someone has to go through "
              "the server node-7 and find out how. That someone is you.\n\n"
              "GUS, the system overseer, welcomes you: \"There is no mouse here. There is only you and a prompt. "
              "Start by finding out where you are standing.\""),
    "learn": ("A terminal is a text window where you control the computer with commands instead of clicks. "
              "Files live in folders, just like in Finder. The difference is that you always stand somewhere, "
              "and that place is called your current folder.\n\n"
              "Three commands are enough to get around:\n"
              "- `pwd` shows where you are.\n"
              "- `ls` shows what is there.\n"
              "- `cd folder` goes into a folder.\n\n"
              "A few shortcuts: `..` means the folder above, `~` is your home folder and `-` is the place you just left. "
              "Press Tab after typing the start of a name and the terminal finishes it for you. "
              "Tab is what makes the terminal faster than clicking."),
    "build": build1,
    "cheats": [("pwd", "show where you are"), ("ls", "list the contents of the folder"),
               ("cd folder", "go into a folder"), ("cd ..", "go up one level"),
               ("cd ~   (or just cd)", "go home"), ("cd -", "go back to where you just were"),
               ("Tab", "finish the name for me")],
    "outro": "GUS: \"You can find your way around. That is more than half of it. Now we are going to read something.\"",
    "missions": [
        {"text": "Find out where you are standing right now.",
         "hints": ["The command is three letters and stands for print working directory.", "Type `pwd` and press Enter."],
         "sol": ["pwd"], "check": lambda g: ran(g, r"^\s*pwd\b"), "xp": 5,
         "after": "`pwd` prints the full path to where you stand. A path that starts with / begins at the root folder of the whole computer."},
        {"text": "List what is in the folder.",
         "hints": ["The command is short for list.", "Type `ls`."],
         "sol": ["ls"], "check": lambda g: ran(g, r"^\s*ls\b"), "xp": 5,
         "after": "`ls` shows files and folders. Folders usually have a different color from files."},
        {"text": "Go into the folder `office`.",
         "hints": ["`cd` means change directory. After it you type the name of the folder.", "Type `cd office`."],
         "sol": ["cd office"], "check": lambda g: g.cwd == g.P("office"), "xp": 5,
         "after": "If you misspell it you get an error and stay where you are. Nothing breaks."},
        {"text": "Go on into `server_room`. Type `cd ser` and press Tab instead of typing the rest.",
         "hints": ["Type just `cd ser` and then press the Tab key.", "Type `cd server_room`."],
         "sol": ["cd server_room"], "check": lambda g: g.cwd == g.P("office/server_room"), "xp": 10,
         "after": "Tab fills in what is unambiguous. If there are several matches, pressing Tab twice lists them all. Experienced users almost never type a whole file name."},
        {"text": "Step back up one level, to `office`.",
         "hints": ["Two dots mean the folder above.", "Type `cd ..`"],
         "sol": ["cd .."], "check": lambda g: re.match(r"^cd\s+\.\./?$", lastcmd(g)) and g.cwd == g.P("office"), "xp": 5,
         "after": "`..` works everywhere. `cd ../..` takes you two levels up, and `ls ..` lists the folder above without moving you."},
        {"text": "Go home, to your home folder, with a short command.",
         "hints": ["The home folder has its own symbol: a tilde.", "Type `cd ~`. Just `cd` with nothing after it works too."],
         "sol": ["cd ~"], "check": lambda g: g.cwd == g.root and lastcmd(g).startswith("cd"), "xp": 5,
         "after": "`~` is always your home folder, wherever you stand. It is the fastest way back when you are lost."},
        {"text": "The archive is in `archive/2020/q4`. Get there with a single `cd` command.",
         "hints": ["You can type the whole way in one go, with slashes between the folders.", "Type `cd archive/2020/q4`. With Tab it goes fast."],
         "sol": ["cd archive/2020/q4"], "check": lambda g: g.cwd == g.P("archive/2020/q4"), "xp": 10,
         "after": "A path like `archive/2020/q4` is called relative, because it starts from where you stand. One that starts with / is called absolute."},
        {"text": "Jump home, then get back to `q4` with a short command that remembers where you were.",
         "hints": ["The minus sign means the previous place.", "Type `cd ~` and then `cd -`."],
         "sol": ["cd ~", "cd -"],
         "check": lambda g: lastcmd(g) == "cd -" and g.cwd == g.P("archive/2020/q4") and any(re.match(r"^cd(\s+~/?)?$", e["cmd"].strip()) for e in g.mh),
         "xp": 10,
         "after": "`cd -` is like the back button in a browser. Handy when you jump between two folders that are far apart."},
        {"text": "How many folders are directly inside `office`? Look with `ls` and answer.",
         "hints": ["You do not need to go there. `ls office` lists that folder from where you stand.", "Type `ls office` and count. Then answer with `answer 3`, if it is three."],
         "sol": ["ls office", ("svar", "3")], "ans": "3", "xp": 10,
         "after": "`ls` can point at another folder. Most commands work that way: the command, then what to do it with."},
    ],
}

# ------------------------------------------------------------ level 2: reading


def build2(g):
    r = random.Random(2)
    W(g, "message.txt",
      "To: new agent\nFrom: GUS\n\nWelcome aboard. Project Norrsken has leaked.\n"
      "I have put logs, reports and attachments in your home folder.\n"
      "Most of it is visible. Not all of it is.\n\n/GUS\n")
    W(g, ".hidden_note", "Backup password for the archive: OWL42\nDelete this before the boss sees it.\n")
    users = ["akarlsson", "mbergman", "jekberg", "pwallin", "sholm", "cdahl", "okarlsson"]
    msgs = ["INFO  session opened for user: %s", "INFO  backup completed (%d files)",
            "WARN  disk space below 20 percent on /data", "INFO  service mailrelay restarted",
            "INFO  certificate renewed for internal.fyrtornet.example", "WARN  slow database query (%d ms)"]
    t = 6 * 3600
    lines = []
    for i in range(239):
        t += r.randint(60, 300)
        m = r.choice(msgs)
        if "%s" in m:
            m = m % r.choice(users)
        elif "%d" in m:
            m = m % r.randint(80, 4000)
        lines.append("2026-09-28 %s %s" % (hms(t % 86400), m))
    lines.append("2026-09-28 23:58:41 INFO  session opened for user: tnilsson")
    W(g, "logs/server.log", "\n".join(lines) + "\n")
    g.S["loglines"] = str(len(lines))
    W(g, "reports/q1.txt", prose(r, 7))
    W(g, "reports/q2.txt", prose(r, 60))
    W(g, "reports/q3.txt", prose(r, 800))
    W(g, "reports/summary.txt", prose(r, 20))
    import base64
    W(g, "attachments/photo", base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="),
      binary=True)
    W(g, "attachments/contacts.txt", "switchboard 08-555 01 00\n")


L2 = {
    "title": "Read like a detective",
    "story": ("GUS has given you read access to the logs on node-7. There is no photo wall and no timeline, "
              "only text files. If you want to find something, you have to read. Luckily the terminal can read for you "
              "in several ways, and none of them changes a single file."),
    "learn": ("Before you change anything, read. The commands here are harmless. They cannot break anything.\n"
              "- `cat file` prints the whole file.\n"
              "- `head file` shows the start and `tail file` the end. With `-n 5` you choose how many lines.\n"
              "- `less file` opens a pager. The arrows scroll, space takes a page and `q` quits.\n"
              "- `wc -l file` counts lines.\n"
              "- `file file` tells you what a file really is, whatever it is called.\n"
              "- `ls -l` shows size and permissions, `ls -a` shows hidden files (the ones starting with a dot) "
              "and `ls -S` sorts by size.\n\n"
              "Flags like `-l` and `-a` can be combined: `ls -la`."),
    "build": build2,
    "cheats": [("cat file", "print the whole file"), ("head -n 5 file", "show the first five lines"),
               ("tail -n 5 file", "show the last five lines"), ("less file", "page through a file (q quits)"),
               ("wc -l file", "count lines"), ("file file", "find out what a file is"),
               ("ls -la", "list everything, hidden too, with details"), ("ls -lS", "sort by size"),
               ("ls -lh", "show sizes in a readable form")],
    "outro": "GUS: \"A good detective reads first and touches later. You are starting to look like one.\"",
    "missions": [
        {"text": "Read GUS's message in `message.txt`.",
         "hints": ["The command that prints a whole file is named after an animal.", "Type `cat message.txt`."],
         "sol": ["cat message.txt"], "check": lambda g: ran(g, r"\bcat\b.*message"), "xp": 5,
         "after": "`cat` prints the contents of a file. The name comes from concatenate, but it is mostly used for reading."},
        {"text": "GUS says not everything is visible. Also show the hidden files in the folder.",
         "hints": ["Files that start with a dot are hidden. A flag to `ls` shows them.", "Type `ls -a`."],
         "sol": ["ls -a"], "check": lambda g: ran(g, r"\bls\b.*\s-\w*a"), "xp": 10,
         "after": "Hidden files have names that start with a dot. Your Mac is full of them, for example `.zshrc`. We come back to that one."},
        {"text": "Read the hidden file. What is the backup password? Answer with `answer <the password>`.",
         "hints": ["It is just `cat` again, but with a name that starts with a dot. Tab helps.", "Type `cat .hidden_note`."],
         "sol": ["cat .hidden_note", ("svar", "OWL42")], "ans": "OWL42", "xp": 10,
         "after": "Hidden does not mean secret. Anyone who types `ls -a` sees everything. Never put a password in a file just because it is hidden."},
        {"text": "Look at the first three lines of `logs/server.log`.",
         "hints": ["`head` shows the start of a file. With `-n` you choose how many lines.", "Type `head -n 3 logs/server.log`."],
         "sol": ["head -n 3 logs/server.log"], "check": lambda g: ran(g, r"\bhead\b.*server"), "xp": 10,
         "after": "Logs are long. `head` and `tail` let you peek at the ends without filling the screen."},
        {"text": "Who logged in last? Look at the end of the log and answer with the username.",
         "hints": ["`tail` is the sibling of `head`, but for the end.", "Type `tail logs/server.log`. The last line names a user."],
         "sol": ["tail logs/server.log", ("svar", "tnilsson")], "ans": "tnilsson", "xp": 10,
         "after": "`tail` is best known for `tail -f`, which follows a log live as it grows. Try it on a real server sometime."},
        {"text": "How many lines does `logs/server.log` have? Let the terminal count and answer with the number.",
         "hints": ["`wc` stands for word count. A flag makes it count lines instead of words.", "Type `wc -l logs/server.log`."],
         "sol": ["wc -l logs/server.log", ("svar", lambda g: g.S["loglines"])], "ans": lambda g: g.S["loglines"], "xp": 10,
         "after": "`wc -l` is one of the most common commands there is. It gets its real power in the next levels, when you chain it with others."},
        {"text": "Which file in `reports` is the largest? Sort by size and answer with the file name.",
         "hints": ["`ls -l` shows size. An extra flag sorts with the largest first.", "Type `ls -lS reports`. Add `h` for readable sizes."],
         "sol": ["ls -lS reports", ("svar", "q3.txt")], "ans": "q3.txt", "xp": 10,
         "after": "Flags can be combined: `ls -lSh` gives a long list, sorted by size, with readable units. The order of the letters rarely matters."},
        {"text": "The file `attachments/photo` has no extension. What kind of file is it? Answer with the file type, one word.",
         "hints": ["There is a command that looks at the contents instead of the name.", "Type `file attachments/photo`. Answer with the first word of the description."],
         "sol": ["file attachments/photo", ("svar", "PNG")], "ans": ["png", "PNG image data"], "xp": 10,
         "after": "The file extension is only a convention. `file` reads the first bytes and knows. Useful when an email has a suspicious attachment."},
        {"text": "Open the whole log with `less` and scroll around. Quit with `q`.",
         "hints": ["`less` opens a file you can scroll in.", "Type `less logs/server.log`, scroll with the arrows, press `q`."],
         "sol": ["less logs/server.log"], "check": lambda g: ran(g, r"\bless\b"), "xp": 10,
         "after": "In `less` you can search: type `/` and a word, then Enter. `n` jumps to the next hit. Like Cmd+F, but for a 100 MB file."},
    ],
}

# ------------------------------------------------------------ level 3: building


def build3(g):
    W(g, "desk/draft_report.txt", "Draft, not finished.\n")
    W(g, "desk/receipt.txt", "Receipt 2026-09-14: coffee beans, 389 kr.\n")
    W(g, "desk/mess.txt", "I was supposed to move this one.\n")
    W(g, "desk/image1.png", "not really an image\n")
    for n in "abcde":
        W(g, "desk/%s.tmp" % n, "temporary file\n")
    W(g, "desk/old/copy1.txt", "old\n")
    W(g, "desk/old/copy2.txt", "old\n")


L3 = {
    "title": "Build, move, clean",
    "story": ("You are done reading. Now you need a place for the evidence. GUS has left you a messy desk: "
              "a handful of temporary files, a folder of old copies and a couple of files in the wrong place. "
              "\"Order in the folder, order in the head\", he says."),
    "learn": ("Now you change things for real.\n"
              "- `mkdir name` creates a folder. With `-p` it creates several levels at once.\n"
              "- `touch file` creates an empty file.\n"
              "- `cp from to` copies. `mv from to` moves, and renames the same way.\n"
              "- `rm file` deletes. With `-r` it deletes a whole folder with its contents.\n"
              "- `echo text > file` writes text to a file. `>>` appends instead of overwriting.\n"
              "- `*` works as a wildcard: `*.tmp` means every file ending in .tmp.\n\n"
              "Warning: `rm` has no trash can. What is gone is gone, and that is true on your real computer too. "
              "Here `:reset` can rebuild the world, but get used to looking with `ls` before you delete."),
    "build": build3,
    "cheats": [("mkdir name", "create a folder"), ("mkdir -p a/b/c", "create several levels at once"),
               ("touch file", "create an empty file"), ("cp from to", "copy"),
               ("mv from to", "move or rename"), ("rm file", "delete a file, no undo"),
               ("rm -r folder", "delete a folder with contents"), ("echo text > file", "write text to a file (overwrites)"),
               ("echo text >> file", "append text to the end of a file"), ("*.tmp", "wildcard: everything ending in .tmp")],
    "outro": "GUS: \"The evidence folder is in order and the desk is clean. Soon I will not be able to get you away from the terminal.\"",
    "missions": [
        {"text": "Create a folder called `evidence` in your home folder.",
         "hints": ["The command is make directory, shortened.", "Type `mkdir evidence`."],
         "sol": ["mkdir evidence"], "check": lambda g: isdir(g, "evidence"), "xp": 5,
         "after": "`mkdir` creates folders. If it already exists the terminal complains and touches nothing."},
        {"text": "Create an empty file `notes.txt` inside `evidence`, without going there.",
         "hints": ["`touch` creates an empty file if it does not exist.", "Type `touch evidence/notes.txt`."],
         "sol": ["touch evidence/notes.txt"], "check": lambda g: isfile(g, "evidence/notes.txt"), "xp": 5,
         "after": "You do not need to stand in the folder. Give the command the full path and it finds the way."},
        {"text": "Copy `desk/receipt.txt` into `evidence`. The original must stay.",
         "hints": ["`cp` takes two things: what to copy and where.", "Type `cp desk/receipt.txt evidence/`."],
         "sol": ["cp desk/receipt.txt evidence/"], "check": lambda g: isfile(g, "evidence/receipt.txt") and isfile(g, "desk/receipt.txt"), "xp": 10,
         "after": "`cp` makes a copy, `mv` moves the original. The only difference is whether something stays at the old place."},
        {"text": "Move `desk/mess.txt` to `evidence` and rename it to `secret.txt` at the same time.",
         "hints": ["`mv` moves. If the target is a new file name, the file is renamed in the same step.", "Type `mv desk/mess.txt evidence/secret.txt`."],
         "sol": ["mv desk/mess.txt evidence/secret.txt"], "check": lambda g: isfile(g, "evidence/secret.txt") and not isfile(g, "desk/mess.txt"), "xp": 10,
         "after": "There is no separate command for renaming. `mv old new` does it."},
        {"text": "Write a line of text to `evidence/log.txt` with `echo` and `>`.",
         "hints": ["`>` sends the output of a command into a file instead of to the screen.", "Type `echo \"Evidence collected\" > evidence/log.txt`."],
         "sol": ["echo \"Evidence collected\" > evidence/log.txt"], "check": lambda g: len(read(g, "evidence/log.txt").strip()) > 0 and ran(g, r">"), "xp": 10,
         "after": "`>` overwrites everything that was there. Write to a file with contents and it disappears. The next mission shows how to avoid that."},
        {"text": "Add one more line to `evidence/log.txt` without erasing the first. The file must have at least two lines.",
         "hints": ["Two arrows in a row append at the end.", "Type `echo \"Line two\" >> evidence/log.txt`."],
         "sol": ["echo \"Line two\" >> evidence/log.txt"],
         "check": lambda g: len(read(g, "evidence/log.txt").strip().splitlines()) >= 2 and ran(g, r">>"), "xp": 10,
         "after": "`>` overwrites, `>>` appends. That difference is behind many lost log files."},
        {"text": "Delete all the `.tmp` files in `desk` with a single command. The other files must stay.",
         "hints": ["With the wildcard `*` you can point out every file that ends the same way.", "Type `rm desk/*.tmp`."],
         "sol": ["rm desk/*.tmp"],
         "check": lambda g: not [f for f in os.listdir(g.P("desk")) if f.endswith(".tmp")] and isfile(g, "desk/draft_report.txt") and isfile(g, "desk/image1.png"), "xp": 15,
         "after": "The shell replaces `*.tmp` with every matching file name before `rm` starts. Run `ls desk/*.tmp` first if you want to see what will disappear."},
        {"text": "Delete the whole folder `desk/old` with everything in it.",
         "hints": ["`rm` refuses folders unless you say it is ok. The flag `-r` means recursive.", "Type `rm -r desk/old`."],
         "sol": ["rm -r desk/old"], "check": lambda g: not isdir(g, "desk/old"), "xp": 10,
         "after": "`rm -r` follows into every subfolder. Never `rm -rf` a path you have not read through. `-f` means do not ask."},
        {"text": "Create the folder structure `projects/norrsken/design/mockups` with a single command.",
         "hints": ["Without a flag `mkdir` fails if the folders in between are missing. There is a flag that creates them.", "Type `mkdir -p projects/norrsken/design/mockups`."],
         "sol": ["mkdir -p projects/norrsken/design/mockups"], "check": lambda g: isdir(g, "projects/norrsken/design/mockups"), "xp": 10,
         "after": "`-p` stands for parents. The whole chain is created, and if it already exists that is not an error. Handy in scripts."},
    ],
}

# ------------------------------------------------------------ level 4: tracking


def build4(g):
    r = random.Random(4)
    sw = lambda n: prose(r, n)
    W(g, "archive/2022/vacation/trip.txt", sw(5) + "We saw norrsken in Abisko, it was lovely.\n")
    W(g, "archive/2022/finance/budget.txt", sw(9))
    W(g, "archive/2023/backup.log", "INFO backup ok\nINFO backup ok\nWARN slow disk\n")
    W(g, "archive/2023/secret_project/plan_b.txt", sw(6))
    W(g, "archive/2023/marketing/campaign.txt", sw(8))
    W(g, "archive/2024/marketing/ideas.txt", sw(4) + "Campaign image: the light of norrsken.\n")
    W(g, "archive/2024/it/inventory.txt", sw(9))
    W(g, "archive/2024/big_backup.bin", b"0" * 300000, binary=True)
    W(g, "archive/2025/hr/minutes_oct.txt", sw(5) + "Item 4: Project Norrsken, confidentiality applies.\n" + sw(3))
    W(g, "archive/2025/hr/recruiting.txt", sw(7))
    W(g, "archive/2025/board/board_meeting.txt", sw(4) + "The launch of Norrsken takes place on 19 October.\n" + sw(4))
    W(g, "archive/2025/it/incidents.txt", sw(10))
    W(g, "notes.md", "# Notes\n" + sw(5))
    W(g, "office/server_room/node7.log", "INFO node-7 started\n")
    for y, seed in (("2024", 41), ("2025", 42)):
        rr = random.Random(seed)
        msgs = ["INFO  service started", "INFO  connection from 10.0.3.%d", "WARN  high memory usage",
                "INFO  cache cleared", "ERROR connection refused from 10.0.3.%d", "ERROR timeout to database"]
        lines = []
        for i in range(120):
            m = rr.choice(msgs)
            if "%d" in m:
                m = m % rr.randint(11, 40)
            lines.append(m)
        if y == "2025":
            k = rr.randint(60, 95)
            lines[k] = "CRITICAL: database not responding"
            g.S["critical"] = str(k + 1)
            g.S["errors"] = str(sum(1 for x in lines if "ERROR" in x))
        W(g, "archive/%s/system.log" % y, "\n".join(lines) + "\n")
    g.S["logs"] = str(sum(1 for p in walk_files(g) if p.endswith(".log")))


L4 = {
    "title": "The bloodhound",
    "story": ("The archive holds thousands of lines of text from four years. Somewhere in that pile are the traces "
              "of the leak, and you do not have time to open every file. \"You do not find the needle by looking at the hay\", "
              "says GUS. \"You ask the terminal to look for one.\""),
    "learn": ("Two commands do most of the searching:\n"
              "- `find where -name \"*.log\"` looks for files by name. Variants: `-type d` only folders, "
              "`-size +100k` only big files.\n"
              "- `grep word file` shows lines that contain a word. `-r` searches a whole folder, `-i` ignores "
              "upper and lower case, `-c` counts hits, `-n` shows line numbers and `-l` shows only file names.\n\n"
              "`.` means here, the folder you stand in. `find . -name x` searches from where you stand.\n"
              "Put quotes around patterns with wildcards, like `\"*.log\"`, so that find interprets it and not the shell."),
    "build": build4,
    "cheats": [("find . -name \"*.log\"", "find files by name"), ("find . -type d", "find only folders"),
               ("find . -size +100k", "find big files"), ("grep word file", "show lines with a word"),
               ("grep -r word .", "search all files under the folder"), ("grep -i", "ignore upper/lower case"),
               ("grep -c / -n / -l", "count / line numbers / file names only")],
    "outro": "GUS: \"The needle is found. Next time, let the terminal do the work before you start browsing.\"",
    "missions": [
        {"text": "How many files ending in `.log` are there in the whole home folder? Answer with the number.",
         "hints": ["`find` searches. First where to search, then `-name` and the pattern.", "Type `find . -name \"*.log\"` and count the lines."],
         "sol": ["find . -name \"*.log\"", ("svar", lambda g: g.S["logs"])], "ans": lambda g: g.S["logs"], "xp": 10,
         "after": "`find` goes through all subfolders by itself. The pattern should be in quotes, otherwise the shell may poke at it."},
        {"text": "There is a folder whose name starts with `secret`. What is it called? Answer with the folder name.",
         "hints": ["`find` can limit itself to folders with `-type d`. Combine it with `-name`.", "Type `find . -type d -name \"secret*\"`."],
         "sol": ["find . -type d -name \"secret*\"", ("svar", "secret_project")], "ans": "secret_project", "xp": 10,
         "after": "`*` means anything. You only needed to know the start of the name."},
        {"text": "How many files mention the word `Norrsken` exactly like that, with a capital N? Answer with the number.",
         "hints": ["`grep -r` searches a whole folder. Add `-l` to get only file names, and count them.", "Type `grep -rl Norrsken .`"],
         "sol": ["grep -rl Norrsken .", ("svar", "2")], "ans": "2", "xp": 15,
         "after": "`grep` distinguishes upper and lower case unless you say otherwise. The next mission shows how to let go of that."},
        {"text": "Count again, but include every spelling regardless of case. How many files?",
         "hints": ["A flag makes `grep` case-insensitive.", "Type `grep -rli norrsken .` and count the lines."],
         "sol": ["grep -rli norrsken .", ("svar", "4")], "ans": "4", "xp": 15,
         "after": "Two of the hits are only about the northern lights in the sky. A good search means reading the results, not just counting them."},
        {"text": "How many lines contain the word `ERROR` in `archive/2025/system.log`? Answer with the number.",
         "hints": ["`grep` can count matching lines for you with a flag.", "Type `grep -c ERROR archive/2025/system.log`."],
         "sol": ["grep -c ERROR archive/2025/system.log", ("svar", lambda g: g.S["errors"])], "ans": lambda g: g.S["errors"], "xp": 10,
         "after": "`-c` counts lines with a hit. If a line has the word twice it still counts once."},
        {"text": "On which line of `archive/2025/system.log` does it say `CRITICAL`? Answer with the line number.",
         "hints": ["A flag prints line numbers in front of each hit.", "Type `grep -n CRITICAL archive/2025/system.log`."],
         "sol": ["grep -n CRITICAL archive/2025/system.log", ("svar", lambda g: g.S["critical"])], "ans": lambda g: g.S["critical"], "xp": 10,
         "after": "`-n` gives line numbers. Handy when you want to open the file in an editor and jump straight there."},
        {"text": "One file in the archive takes up far too much space. Find the one larger than 100 kilobytes and answer with the file name.",
         "hints": ["`find` can filter on size. Plus means larger than, and `k` means kilobyte.", "Type `find . -size +100k`."],
         "sol": ["find . -size +100k", ("svar", "big_backup.bin")], "ans": "big_backup.bin", "xp": 15,
         "after": "`find . -size +100M` is something you will run when the disk is full and you wonder why."},
    ],
}

# ------------------------------------------------------------ level 5: pipes


def build5(g):
    seed = 50
    while True:
        r = random.Random(seed)
        seed += 1
        users = ["tnilsson", "mbergman", "akarlsson", "jekberg", "pwallin", "sholm", "okarlsson", "cdahl"]
        ips = ["10.0.3.%d" % i for i in range(11, 21)]
        ev = []
        for _ in range(300):
            a = r.choices(["LOGIN_OK", "LOGIN_FAILED", "FILE_READ", "LOGOUT"], [30, 5, 45, 20])[0]
            ev.append((r.randint(6 * 3600, 23 * 3600 + 1100), r.choice(ips), r.choice(users), a))
        for _ in range(56):
            ev.append((r.randint(84000, 85619), "185.12.9.77", "lfalk", "LOGIN_FAILED"))
        ev.append((85620, "185.12.9.77", "lfalk", "LOGIN_OK"))
        for k in range(3):
            ev.append((85700 + k * 40, "185.12.9.77", "lfalk", "FILE_READ"))
        ev.sort()
        lines = ["2026-09-28 %s %s %s %s" % (hms(t), ip, u, a) for t, ip, u, a in ev]
        ipc = Counter(e[1] for e in ev).most_common()
        failc = Counter(e[2] for e in ev if e[3] == "LOGIN_FAILED").most_common()
        if ipc[0][1] > ipc[1][1] and ipc[2][1] > ipc[3][1] and failc[0][1] > failc[1][1]:
            break
    W(g, "logs/access.log", "\n".join(lines) + "\n")
    g.S.update(nlines=str(len(lines)), topip=ipc[0][0], top3=[x[0] for x in ipc[:3]],
               nfailed=sum(1 for x in ev if x[3] == "LOGIN_FAILED"), topfail=failc[0][0])
    people = ([("Operations", 42000)] * 7 + [("Marketing", 39000)] * 5 + [("Finance", 44000)] * 4
              + [("Support", 36000)] * 3 + [("Management", 65000)] * 2)
    names = ["Tomas Nilsson", "Maria Bergman", "Anders Karlsson", "Johanna Ekberg", "Per Wallin", "Sara Holm",
             "Olof Karlsson", "Cecilia Dahl", "Lena Falk", "Karin Lund", "Nils Persson", "Eva Sjo", "Johan Berg",
             "Ida Oberg", "Rasmus Ek", "Mia Hedlund", "Ola Strom", "Anna Viklund", "Hugo Mard", "Elin Nord",
             "Kurt Gran"]
    rows = ["name,department,salary"]
    for n, (d, s) in zip(names, people):
        rows.append("%s,%s,%d" % (n, d, s + r.randint(0, 20) * 100))
    W(g, "personnel.csv", "\n".join(rows) + "\n")
    g.S["topdept"] = "Operations"


L5 = {
    "title": "Pipes",
    "story": ("You now have an access log with 360 lines. No human reads it, but the terminal can. "
              "The secret is that commands can be chained: the output of one becomes the input of the next. "
              "\"It is called a pipe\", says GUS. \"Think Lego. Each command does one small thing. Together they do anything.\""),
    "learn": ("Two tools make the terminal powerful:\n"
              "- `|` (pipe, the key is Alt+7 on a Swedish keyboard) sends the output of the left command into the right command.\n"
              "- `>` sends the output to a file instead of the screen. `>>` appends.\n\n"
              "The building blocks you chain:\n"
              "- `sort` sorts lines. `sort -rn` sorts numbers, largest first.\n"
              "- `uniq -c` merges identical lines next to each other and counts them. Always sort first.\n"
              "- `cut -d' ' -f3` picks column 3 when columns are separated by spaces. `-d,` for commas.\n"
              "- `head -n 3` keeps the first three lines.\n\n"
              "The pattern for \"count what appears most\" is: `... | sort | uniq -c | sort -rn | head`. "
              "You will use it your whole life."),
    "build": build5,
    "cheats": [("command1 | command2", "chain: output becomes input"), ("command > file", "save the output in a file"),
               ("sort / sort -rn", "sort / sort numbers, largest first"), ("uniq -c", "count identical lines (sort first)"),
               ("cut -d' ' -f3", "pick column 3, split on spaces"), ("cut -d, -f2", "pick column 2 in a csv"),
               ("... | sort | uniq -c | sort -rn | head", "top list of what appears most")],
    "outro": "GUS: \"We now know who was hammering on the door. You know the pattern for lists like that by heart.\"",
    "missions": [
        {"text": "Count the lines in `logs/access.log`, but this time with a pipe: send the file through `cat` into `wc -l`.",
         "hints": ["Type the command that reads the file, then the character `|`, then the command that counts.", "Type `cat logs/access.log | wc -l`."],
         "sol": ["cat logs/access.log | wc -l"], "check": lambda g: ran(g, r"\|\s*wc"), "xp": 10,
         "after": "This is what a pipe looks like. `cat` prints, `|` passes it on, `wc` counts. Each tool does one thing."},
        {"text": "Which IP address appears most often in the log? Column 3 is the IP address. Answer with the address.",
         "hints": ["Pick column 3, sort, count identical lines, sort by count, take the top line.", "Type `cut -d' ' -f3 logs/access.log | sort | uniq -c | sort -rn | head -1`."],
         "sol": ["cut -d' ' -f3 logs/access.log | sort | uniq -c | sort -rn | head -1", ("svar", lambda g: g.S["topip"])],
         "ans": lambda g: g.S["topip"], "xp": 20,
         "after": "That is the classic top list. Four small commands, and you have the answer to something that would take a quarter of an hour in a spreadsheet."},
        {"text": "Save all lines with `FAILED` in a new file `failed.txt`.",
         "hints": ["`grep` finds the lines. `>` sends the result to a file.", "Type `grep FAILED logs/access.log > failed.txt`."],
         "sol": ["grep FAILED logs/access.log > failed.txt"],
         "check": lambda g: len(read(g, "failed.txt").strip().splitlines()) == g.S["nfailed"] and ran(g, r">"), "xp": 15,
         "after": "Now you have a file to pass on, or to work on further. What is hard to do in a graphical interface is trivial here."},
        {"text": "Which user has the most failed logins? The username is in column 4. Answer with the name.",
         "hints": ["Start with `grep FAILED`, pick column 4, and then the same top list as before.", "Type `grep FAILED logs/access.log | cut -d' ' -f4 | sort | uniq -c | sort -rn | head -1`."],
         "sol": ["grep FAILED logs/access.log | cut -d' ' -f4 | sort | uniq -c | sort -rn | head -1", ("svar", lambda g: g.S["topfail"])],
         "ans": lambda g: g.S["topfail"], "xp": 20,
         "after": "Six commands in a row, and you have a name. Note it. Someone tried to get in much harder than everyone else."},
        {"text": "In `personnel.csv` the department is column 2, with a comma as the separator. Which department has the most employees? Answer with the name.",
         "hints": ["`cut` has a flag for the separator, `-d,`. Then the same top list.", "Type `cut -d, -f2 personnel.csv | sort | uniq -c | sort -rn | head -3`."],
         "sol": ["cut -d, -f2 personnel.csv | sort | uniq -c | sort -rn | head -3", ("svar", "Operations")], "ans": "Operations", "xp": 15,
         "after": "The same pattern works on any column, in any file. Try it on an export from a system you work with."},
        {"text": "Save the three most common IP addresses, with counts, in a file `topip.txt`.",
         "hints": ["You already have the list from mission 2. Make it give three lines instead of one and send it to a file.", "Type `cut -d' ' -f3 logs/access.log | sort | uniq -c | sort -rn | head -3 > topip.txt`."],
         "sol": ["cut -d' ' -f3 logs/access.log | sort | uniq -c | sort -rn | head -3 > topip.txt"],
         "check": lambda g: (lambda ls: len(ls) == 3 and set(l.split()[-1] for l in ls) == set(g.S["top3"]))(read(g, "topip.txt").strip().splitlines()),
         "xp": 20,
         "after": "You have built your first real pipeline. It can be saved as an alias or a script, and we do that later."},
    ],
}

# ------------------------------------------------------------ level 6: permissions


def build6(g):
    W(g, "tools/decode.sh",
      '#!/bin/bash\necho "Decoding signal from node-7..."\necho "CODE: $(rev < "$(dirname "$0")/signal.txt")"\n',
      mode=0o644)
    W(g, "tools/signal.txt", "LWOTHGIN\n")
    W(g, "secret.key", "the key to the server room\n", mode=0o777)


L6 = {
    "title": "Permissions and scripts",
    "story": ("GUS has found a script that is supposed to decode a signal from the server. It is not executable. The key to the "
              "server room also sits in a file that anyone may read. \"That is exactly how leaks begin\", he says. "
              "\"Fix it.\""),
    "learn": ("Every file has permissions for three groups: the owner, the group and everyone else. Each group can get read (r), "
              "write (w) and execute (x). `ls -l` shows them at the start of the line:\n"
              "$ -rwxr-xr--   1 agent  staff  120 ...\n"
              "Read it like this: the first character is the type (- file, d folder). Then three groups of three characters: `rwx` for the owner, "
              "`r-x` for the group, `r--` for everyone else.\n\n"
              "- `chmod +x file` makes a file executable.\n"
              "- `chmod 600 file` gives only the owner read and write. The numbers are r=4, w=2, x=1 and are added per group: "
              "6 is 4+2, that is rw.\n"
              "- `./script.sh` runs a file in the folder you stand in. The dot and the slash are needed.\n\n"
              "A script is a text file whose first line, the shebang, says which program should run it: "
              "`#!/bin/bash`."),
    "build": build6,
    "cheats": [("ls -l", "show permissions, owner and size"), ("chmod +x file", "make the file executable"),
               ("chmod 600 file", "only the owner may read and write"), ("chmod 755 file", "owner everything, others read and run"),
               ("./script.sh", "run a script in the current folder"), ("#!/bin/bash", "first line of a script")],
    "outro": "GUS: \"Now the key is locked and the script runs. Writing your own scripts is like giving the terminal a memory.\"",
    "missions": [
        {"text": "Look at the permissions of the files in `tools`. What is the permission string of `decode.sh`? Answer with the ten characters, for example `-rwxr-xr-x`.",
         "hints": ["`ls -l` shows the permissions at the far left.", "Type `ls -l tools` and read the line for decode.sh."],
         "sol": ["ls -l tools", ("svar", "-rw-r--r--")], "ans": "-rw-r--r--", "xp": 10,
         "after": "`rw-` for the owner, `r--` for the group and `r--` for everyone else. No x anywhere, so the file can be read but not run."},
        {"text": "Try to run `decode.sh` with `./tools/decode.sh`. It will fail. That is the point.",
         "hints": ["Type the path to the file with `./` in front.", "Type `./tools/decode.sh`."],
         "sol": ["./tools/decode.sh"], "check": lambda g: ranfail(g, r"decode\.sh"), "xp": 5,
         "after": "Permission denied. The terminal refuses because the file lacks x. There is nothing wrong with the script."},
        {"text": "Make `tools/decode.sh` executable.",
         "hints": ["`chmod` changes permissions. Plus x adds the right to run.", "Type `chmod +x tools/decode.sh`."],
         "sol": ["chmod +x tools/decode.sh"], "check": lambda g: mode(g, "tools/decode.sh") & 0o100, "xp": 10,
         "after": "Check with `ls -l tools`. Now there is an x on the line."},
        {"text": "Run the script. What code does it print? Answer with the code.",
         "hints": ["The same command as before, now that it is allowed to run.", "Type `./tools/decode.sh`."],
         "sol": ["./tools/decode.sh", ("svar", "NIGHTOWL")], "ans": "NIGHTOWL", "xp": 10,
         "after": "You ran a program you can read yourself. Open it with `cat tools/decode.sh` and see how little it is."},
        {"text": "The key file `secret.key` is readable by everyone. Make sure only you can read and write it, and that nobody else gets anything.",
         "hints": ["The number 600 gives the owner rw and nobody else anything.", "Type `chmod 600 secret.key`."],
         "sol": ["chmod 600 secret.key"], "check": lambda g: (mode(g, "secret.key") & 0o077) == 0 and (mode(g, "secret.key") & 0o600) == 0o600, "xp": 15,
         "after": "That is how you treat private keys. SSH actually refuses to use a key file that others can read."},
        {"text": "Write your own script `hello.sh` that prints a greeting. It must have a shebang, be executable, and you must run it.",
         "hints": ["Three steps: write `#!/bin/bash` on the first line with `echo ... >`, add a line with `>>`, run `chmod +x` and then `./hello.sh`.",
                   "Type:\n$ echo '#!/bin/bash' > hello.sh\n$ echo 'echo hello from the terminal' >> hello.sh\n$ chmod +x hello.sh\n$ ./hello.sh"],
         "sol": ["echo '#!/bin/bash' > hello.sh", "echo 'echo hello from the terminal' >> hello.sh", "chmod +x hello.sh", "./hello.sh"],
         "check": lambda g: isfile(g, "hello.sh") and read(g, "hello.sh").startswith("#!") and (mode(g, "hello.sh") & 0o100)
                            and any(e["ec"] == 0 and re.match(r"^(\./|~/|\S*/)?hello\.sh(\s|$)", e["cmd"].strip()) for e in g.mh),
         "xp": 25,
         "after": "You have written a program. Anything you can do in the terminal can be saved in a script and run with one command."},
    ],
}

# ------------------------------------------------------------ level 7: environment and processes


def build7(g):
    W(g, "tools/hello", '#!/bin/bash\necho "Hello from tools. You ran this without a path thanks to PATH."\n', mode=0o755)
    W(g, "notes.txt", "Something is running on the server and it should not be.\n")
    D(g, "projects")
    spawn_spok(g)


L7 = {
    "title": "Environment and processes",
    "story": ("The alarm on node-7 shows high load. GUS suspects a program running in the background that should not be. "
              "\"One of them is called spok\", he says. \"That does not sound like anything we installed.\" Before you find it "
              "you need to understand how the terminal remembers things."),
    "learn": ("The terminal has a memory called the environment.\n"
              "- `export NAME=value` creates a variable. `echo $NAME` prints it.\n"
              "- `alias ll='ls -l'` creates a shortcut. Then type `ll`.\n"
              "- `PATH` is a list of folders where the terminal looks for commands. If you add a folder to `PATH`, the programs in it "
              "can be run without a path.\n\n"
              "Processes are programs running right now:\n"
              "- `ps aux` lists them all. Pipe it through `grep name` to find one.\n"
              "- `kill PID` asks a process to quit. PID is the number in the second column of `ps aux`.\n"
              "- `pgrep name` prints just the number. And `$(command)` is replaced by whatever the command prints, "
              "so `kill $(pgrep spok)` finds and stops it in one go.\n\n"
              "This level breaks a rule: we touch real processes. Only kill the one the game points out."),
    "build": build7,
    "cheats": [("export NAME=value", "create a variable"), ("echo $NAME", "print a variable"),
               ("alias ll='ls -l'", "create a shortcut"), ("export PATH=$PATH:~/folder", "add a folder to the command list"),
               ("ps aux | grep name", "find a process"), ("pgrep name", "print the PID of a process"),
               ("kill PID", "ask a process to quit"), ("$(command)", "replace with the output of the command")],
    "outro": "GUS: \"Spok is gone. You now know how the terminal remembers, and how to shut down something that should not run.\"",
    "missions": [
        {"text": "Print what the variable `HOME` contains.",
         "hints": ["Variables are printed with `echo` and a dollar sign in front of the name.", "Type `echo $HOME`."],
         "sol": ["echo $HOME"], "check": lambda g: ran(g, r"echo\s+.*\$\{?HOME"), "xp": 5,
         "after": "The dollar sign means replace with the value. `echo $USER`, `echo $PATH` and `echo $SHELL` show others."},
        {"text": "Create a variable of your own, `CODENAME`, with any value.",
         "hints": ["Type `export`, then the name, an equals sign and the value. No spaces around the equals sign.", "Type `export CODENAME=owl`."],
         "sol": ["export CODENAME=owl"], "check": lambda g: re.search(r'CODENAME="?\w', state(g, "env")), "xp": 10,
         "after": "`export` makes the variable available to programs you start. That is how most things are configured: API keys, language and colors."},
        {"text": "Print your new variable `CODENAME`.",
         "hints": ["Same thing as with `HOME`.", "Type `echo $CODENAME`."],
         "sol": ["echo $CODENAME"], "check": lambda g: ran(g, r"echo\s+.*\$\{?CODENAME"), "xp": 5,
         "after": "The variable stays between commands, but only in this window. A new terminal window starts from zero. We fix that in the next level."},
        {"text": "Create a shortcut `ll` that runs `ls -l`.",
         "hints": ["`alias`, then the name, an equals sign and the command inside quotes.", "Type `alias ll='ls -l'`."],
         "sol": ["alias ll='ls -l'"], "check": lambda g: re.search(r"^alias ll=", state(g, "alias"), re.M), "xp": 10,
         "after": "Only what you type often is worth a shortcut. A long list of a long command is a good sign for an alias."},
        {"text": "Use your shortcut: type `ll`.",
         "hints": ["Just type the name of the alias.", "Type `ll`."],
         "sol": ["ll"], "check": lambda g: any(e["ec"] == 0 and re.match(r"^ll\b", e["cmd"].strip()) for e in g.mh), "xp": 5,
         "after": "That saved five characters. Multiply by a hundred times a day."},
        {"text": "Put the folder `tools` in your `PATH`, so you can run the program `hello` in it without typing a path. Then run `hello`.",
         "hints": ["`export PATH=$PATH:...` adds a folder at the end of the list. `~/tools` is the folder.", "Type `export PATH=$PATH:~/tools` and then `hello`."],
         "sol": ["export PATH=$PATH:~/tools", "hello"],
         "check": lambda g: g.root + "/tools" in state(g, "env") and any(e["ec"] == 0 and e["cmd"].strip() == "hello" for e in g.mh), "xp": 20,
         "after": "That is how it works when you install a program: a tool sits in a folder that is in PATH. Now you know why."},
        {"text": "Something called `spok` is running in the background. Find it, and answer with its PID. The PID is the number in the second column.",
         "hints": ["`ps aux` lists all processes. Pipe it through `grep spok` to see only yours.", "Type `ps aux | grep spok`. Take the number on the line where spok runs, not the line for grep."],
         "sol": ["ps aux | grep spok", ("svar", lambda g: g.S["pid"])], "ans": lambda g: str(g.S["pid"]), "xp": 15,
         "after": "You will always see an extra line for `grep` itself in searches like this. Knowing that is half the win."},
        {"text": "Stop the process `spok`.",
         "hints": ["`kill` followed by the PID. Or `pgrep spok`, which gives you the number.", "Type `kill PID` with the number you found."],
         "sol": ["kill $(pgrep spok)"], "check": lambda g: bool(g.procs) and g.procs[0].poll() is not None, "xp": 20,
         "after": "`kill` asks the process to quit. If it hangs around there is `kill -9 PID`, but always try the polite way first."},
    ],
}

# ------------------------------------------------------------ level 8: make it yours


def build8(g):
    D(g, "projects")
    D(g, "tools")
    W(g, "example_zshrc.txt", """# This is what a real ~/.zshrc can look like. Everything here runs every time you open a terminal window.

# Navigation
alias ..='cd ..'
alias ...='cd ../..'
alias ll='ls -lah'
alias projects='cd ~/Documents/projects'

# Safer
alias rm='rm -i'
alias cp='cp -i'

# Things you would otherwise google every time
alias myip='curl -s ifconfig.me'
alias weather='curl -s "wttr.in/Stockholm?format=3"'
alias ports='lsof -i -P | grep LISTEN'
alias sizes='du -sh * | sort -h'
alias serve='python3 -m http.server 8000'
alias clean='find . -name ".DS_Store" -delete'
alias findin='grep -rn'

# Git
alias gs='git status -sb'
alias gl='git log --oneline --graph -15'

# Functions: like aliases, but with arguments and several steps
mkcd() { mkdir -p "$1" && cd "$1"; }
backup() { cp "$1" "$1.bak-$(date +%F)"; }
update() { brew update && brew upgrade; }

# Environment
export EDITOR=nano
export HISTSIZE=10000
export PATH="$HOME/bin:$PATH"

# Prompt: folder in cyan, then a dollar sign
export PS1='\\[\\e[36m\\]\\w\\[\\e[0m\\] \\$ '
""")


def _rc(g):
    return read(g, ".myrc")


L8 = {
    "title": "Make it yours",
    "story": ("GUS looks at you over the rim of his coffee cup. \"You type the same things over and over. Everyone does. "
              "The difference is that people who know the terminal rebuild it until it types for them.\" "
              "Here you get your own terminal: your own shortcuts, your own prompt and your own small functions."),
    "learn": ("The terminal reads a file every time it starts. On your Mac it is called `~/.zshrc`. Everything you write in it applies "
              "in every new window. Here in the game you have your own, `.myrc`, and you load it with `source .myrc`.\n\n"
              "What you can put in it:\n"
              "- aliases for everything you type often: `alias gs='git status'`\n"
              "- functions, which are aliases with arguments: `mkcd() { mkdir -p \"$1\" && cd \"$1\"; }`\n"
              "- variables: `export EDITOR=nano`\n"
              "- the prompt, the text before the cursor, in the variable `PS1`. `\\w` is the folder, `\\u` your name and `\\e[35m` "
              "turns the rest magenta. Change the prompt in the game and you see it right below.\n\n"
              "The file `example_zshrc.txt` in your home folder is a real config that shows how far it goes: weather, "
              "your IP address, a local web server, git shortcuts, a safer `rm`, backup with a date. "
              "Read it when you are done with the first part. You can take what you like."),
    "build": build8,
    "cheats": [("alias name='command'", "create a shortcut"), ("unalias -a", "remove all shortcuts for now"),
               ("source .myrc", "reload a config file"), ("PS1='...'", "change the prompt"),
               ("name() { ...; }", "create a function"), ("echo '...' >> file", "build a config file line by line"),
               ("~/.zshrc", "your real config file on a Mac")],
    "outro": ("GUS: \"Now your terminal looks like yours. The file `.myrc` is in your home folder. On your real Mac the equivalent is "
              "`~/.zshrc`. Paste in what you want, run `source ~/.zshrc`, and you have the same shortcuts everywhere. "
              "I have saved a ready copy for you in `~/.terminalspelet/min_zshrc.txt`.\""),
    "on_done": lambda g: shutil.copy(g.P(".myrc"), os.path.join(os.path.dirname(g.root), "min_zshrc.txt")) if isfile(g, ".myrc") else None,
    "missions": [
        {"text": "Create a shortcut `home` that takes you to your home folder.",
         "hints": ["`alias`, then the name, an equals sign and the command inside quotes. The command is what you learned in level 1.", "Type `alias home='cd ~'`."],
         "sol": ["alias home='cd ~'"], "check": lambda g: re.search(r"^alias home='cd", state(g, "alias"), re.M), "xp": 10,
         "after": "The shortcut now exists in this window. A new window does not have it, until we save it."},
        {"text": "First go into the folder `projects`. Then use your new shortcut to get home.",
         "hints": ["Do `cd projects`, then just type the name of the shortcut.", "Type `cd projects` and then `home`."],
         "sol": ["cd projects", "home"],
         "check": lambda g: lastcmd(g) == "home" and g.last["ec"] == 0 and g.last["before"] != g.root and g.cwd == g.root, "xp": 5,
         "after": "You can write your own versions of anything. Some people add a shortcut for every project folder they work in."},
        {"text": "Save at least two aliases in the file `.myrc` in your home folder, for example `ll` and `home`. Build the file line by line with `echo` and `>>`.",
         "hints": ["You have had `>>` since level 3. Each line should be an alias, quoted with single quotes.",
                   "Type:\n$ echo \"alias ll='ls -lah'\" >> .myrc\n$ echo \"alias home='cd ~'\" >> .myrc"],
         "sol": ["echo \"alias ll='ls -lah'\" >> .myrc", "echo \"alias home='cd ~'\" >> .myrc"],
         "check": lambda g: len(re.findall(r"^alias \S+=", _rc(g), re.M)) >= 2, "xp": 15,
         "after": "Real config files work the same way: lines with commands that run every time you start. You just created one."},
        {"text": "Simulate restarting the terminal. First remove all aliases with `unalias -a`, then reload them from the file with `source .myrc`.",
         "hints": ["Two commands in order. The first clears, the second reads the file.", "Type `unalias -a` and then `source .myrc`."],
         "sol": ["unalias -a", "source .myrc"],
         "check": lambda g: (lambda u, s: u is not None and s is not None and s > u
                             and re.search(r"^alias ll=", state(g, "alias"), re.M) and re.search(r"^alias home=", state(g, "alias"), re.M))(
             next((i for i, e in enumerate(g.mh) if e["ec"] == 0 and re.search(r"\bunalias\b", e["cmd"])), None),
             next((i for i, e in enumerate(g.mh) if e["ec"] == 0 and re.match(r"^(source|\.)\s+\S*\.myrc", e["cmd"].strip())), None)),
         "xp": 15,
         "after": "`source` runs a file in the current shell. On your Mac the terminal does exactly that with `~/.zshrc` when a window opens."},
        {"text": "Change your prompt. Set `PS1` to something that contains the folder (`\\w`) and a color. The game's prompt changes immediately.",
         "hints": ["`\\w` is the current folder. `\\[\\e[35m\\]` starts magenta and `\\[\\e[0m\\]` ends it. Put the whole value inside single quotes.",
                   "Type `PS1='\\[\\e[35m\\]\\w ▸ \\[\\e[0m\\]'`. Then try changing the color number: 31 red, 32 green, 33 yellow, 34 blue, 36 cyan."],
         "sol": ["PS1='\\[\\e[35m\\]\\w ▸ \\[\\e[0m\\]'"],
         "check": lambda g: re.search(r"\\[wW]", state(g, "ps1")) and re.search(r"\\(e|033)\[", state(g, "ps1")), "xp": 20,
         "after": "The prompt is what you look at all day. Some people add the git branch, the time or the exit code of the last command. The tool Starship does it with a couple of lines."},
        {"text": "Write a function `mkcd` that creates a folder and goes into it. Test it with `mkcd lab/test`.",
         "hints": ["A function: `name() { command1 && command2; }`. `$1` is the first argument you type after the name.",
                   "Type `mkcd() { mkdir -p \"$1\" && cd \"$1\"; }` and then `mkcd lab/test`."],
         "sol": ["mkcd() { mkdir -p \"$1\" && cd \"$1\"; }", "mkcd lab/test"],
         "check": lambda g: "mkcd" in state(g, "funcs") and any(e["ec"] == 0 and re.match(r"^mkcd\s+\S+", e["cmd"].strip()) for e in g.mh)
                            and g.cwd != g.root and os.path.isdir(g.cwd), "xp": 25,
         "after": "A function is an alias that can take arguments and run several steps. Almost everyone has an `mkcd` somewhere in their config."},
        {"text": "Read `example_zshrc.txt`. Which alias there starts a local web server? Answer with the name of the alias.",
         "hints": ["Open the file with what you learned in level 2.", "Type `cat example_zshrc.txt`. Look for `python3 -m http.server`."],
         "sol": ["cat example_zshrc.txt", ("svar", "serve")], "ans": "serve", "xp": 10,
         "after": "That is a fraction of what is possible. You can put the weather in the prompt, have a command that clears Downloads or one that creates a new project folder with the right files. It all starts with an alias."},
        {"text": "Go home with `cd ~`. Then finish your config: add a `PS1` line and at least one `export` line to `.myrc`, so the file has aliases, a prompt and a variable.",
         "hints": ["Use `echo` and `>>` as before. Put the line inside single quotes so that the backslashes come along.",
                   "Type:\n$ echo 'PS1=\"\\[\\e[35m\\]\\w ▸ \\[\\e[0m\\] \"' >> .myrc\n$ echo 'export EDITOR=nano' >> .myrc"],
         "sol": ["cd ~", "echo 'PS1=\"\\[\\e[35m\\]\\w ▸ \\[\\e[0m\\] \"' >> .myrc", "echo 'export EDITOR=nano' >> .myrc"],
         "check": lambda g: re.search(r"^(export )?PS1=", _rc(g), re.M) and re.search(r"^export \w+=", _rc(g), re.M)
                            and len(re.findall(r"^alias \S+=", _rc(g), re.M)) >= 2, "xp": 20,
         "after": "Done. A copy of your file is saved when the level ends, so you can paste it into `~/.zshrc` for real."},
    ],
}

# ------------------------------------------------------------ level 9: the toolbox


def build9(g):
    r = random.Random(9)
    for n in ("a_draft", "b_attachment", "c_note", "d_meetings", "e_agenda"):
        W(g, "docs/%s.txt" % n, prose(r, 4))
    W(g, "plan.txt", "Launch of Norrsken in October.\nBudget for Norrsken is locked.\nOnly the board knows about Norrsken.\nAgenda follows.\n")
    posts = [("Advertising", "marketing", 45000), ("Web", "marketing", 22000), ("Licenses", "it", 18000),
             ("Consultant", "it", 60000), ("Travel", "operations", 9500), ("Training", "operations", 12500),
             ("Event", "marketing", 31000), ("Hosting", "it", 14000)]
    W(g, "budget.csv", "item,category,amount\n" + "\n".join("%s,%s,%d" % p for p in posts) + "\n")
    g.S["total"] = str(sum(p[2] for p in posts))
    for i in range(12):
        W(g, "tmp/%s/file%d.tmp" % (r.choice(["a", "b", "c"]), i), "junk\n")
    W(g, "tmp/a/keep.keep", "keep me\n")
    W(g, "tmp/b/keep2.keep", "keep me too\n")


def _keeps(g):
    return len([1 for p in walk_files(g) if p.endswith(".keep")])


L9 = {
    "title": "The toolbox",
    "story": ("The leak is almost found, but first you need to clean up after yourself and scrub a plan so it can be shared. "
              "\"Now you get to see what the terminal can do when you stop doing one thing at a time\", says GUS. "
              "\"Loops, text replacement, sums and packed files. And no, it is not harder than what you already know.\""),
    "learn": ("These tools are what make professionals look like magicians.\n"
              "- `for f in *.txt; do command \"$f\"; done` runs a command on every file that matches.\n"
              "- `sed 's/old/new/g' file` replaces text. The output goes to the screen, so add `> newfile`.\n"
              "- `awk -F, '{s+=$3} END {print s}' file` sums column 3 of a csv file. `NR>1` skips the header line.\n"
              "- `find . -name \"*.tmp\" -delete` finds and deletes in the same step.\n"
              "- `a && b` runs b only if a succeeded. `a || b` runs b only if a failed.\n"
              "- `$(command)` is replaced by the output of the command. `$(date +%F)` becomes today's date.\n"
              "- `tar -czf archive.tar.gz folder` packs a folder into a file. `tar -xzf archive.tar.gz` unpacks."),
    "build": build9,
    "cheats": [("for f in *.txt; do ...; done", "run something on every file"), ("sed 's/a/b/g' file", "replace text"),
               ("awk -F, '{s+=$3} END {print s}' file", "sum a column"), ("find . -name \"*.tmp\" -delete", "find and delete"),
               ("a && b", "run b only if a went well"), ("$(date +%F)", "today's date, 2026-09-29"),
               ("tar -czf x.tar.gz folder", "pack a folder"), ("tar -xzf x.tar.gz", "unpack")],
    "outro": "GUS: \"Loops, text replacement, sums and archives. You now have more tools than most people who say they know the terminal.\"",
    "missions": [
        {"text": "All files in `docs` end in `.txt`. Change the extension to `.md` on all of them at once with a `for` loop.",
         "hints": ["The loop goes through the files. `${f%.txt}` removes `.txt` from the name in `f`.",
                   "Type `for f in docs/*.txt; do mv \"$f\" \"${f%.txt}.md\"; done`."],
         "sol": ["for f in docs/*.txt; do mv \"$f\" \"${f%.txt}.md\"; done"],
         "check": lambda g: len([f for f in os.listdir(g.P("docs")) if f.endswith(".md")]) == 5 and not [f for f in os.listdir(g.P("docs")) if f.endswith(".txt")],
         "xp": 25, "after": "Imagine 500 files instead of 5. It takes just as long to type."},
        {"text": "`plan.txt` mentions `Norrsken` and is going to be shared. Create `plan_clean.txt` where the word has been replaced by `PROJECT-X`. The original must stay untouched.",
         "hints": ["`sed 's/old/new/g'` replaces all occurrences. Send the result to a new file.", "Type `sed 's/Norrsken/PROJECT-X/g' plan.txt > plan_clean.txt`."],
         "sol": ["sed 's/Norrsken/PROJECT-X/g' plan.txt > plan_clean.txt"],
         "check": lambda g: isfile(g, "plan_clean.txt") and "Norrsken" not in read(g, "plan_clean.txt") and "PROJECT-X" in read(g, "plan_clean.txt") and "Norrsken" in read(g, "plan.txt"),
         "xp": 20, "after": "`sed` is a find and replace that works on files of any size."},
        {"text": "What is the sum of the column `amount` in `budget.csv`? Skip the header line. Answer with the number.",
         "hints": ["`awk` can calculate. `-F,` says the columns are separated by commas, `NR>1` skips the first line.",
                   "Type `awk -F, 'NR>1 {s+=$3} END {print s}' budget.csv`."],
         "sol": ["awk -F, 'NR>1 {s+=$3} END {print s}' budget.csv", ("svar", lambda g: g.S["total"])], "ans": lambda g: g.S["total"], "xp": 25,
         "after": "`awk` is a whole small programming language. What you just did was a single line out of a spreadsheet formula."},
        {"text": "Delete all `.tmp` files in `tmp` and all its subfolders, with a single command. The files ending in `.keep` must stay.",
         "hints": ["`find` with `-name` finds them. Add an action at the end that deletes them.", "Type `find tmp -name \"*.tmp\" -delete`."],
         "sol": ["find tmp -name \"*.tmp\" -delete"],
         "check": lambda g: not [p for p in walk_files(g) if p.endswith(".tmp")] and _keeps(g) == 2, "xp": 20,
         "after": "Always run `find ...` without `-delete` first to see what will disappear. Then swap it in."},
        {"text": "Create the folder `work` and go into it, in a single command line. The second command must only run if the first succeeded.",
         "hints": ["`&&` joins two commands so that the second only runs if the first succeeds.", "Type `mkdir work && cd work`."],
         "sol": ["mkdir work && cd work"], "check": lambda g: g.cwd == g.P("work"), "xp": 10,
         "after": "`&&` keeps you from carrying on in the wrong folder when something went wrong. It is the seat belt of scripts."},
        {"text": "Go home. Create a folder called `backup_` followed by today's date, using `$(date +%F)`.",
         "hints": ["`date +%F` prints the date as 2026-09-29. `$(...)` replaces itself with that.", "Type `mkdir backup_$(date +%F)`, after `cd ~`."],
         "sol": ["cd ~", "mkdir backup_$(date +%F)"],
         "check": lambda g: any(os.path.basename(d) == "backup_" + time.strftime("%Y-%m-%d") for d in walk_dirs(g)), "xp": 15,
         "after": "That is how daily backups get unique names without anyone making one up. A date in file names is a good habit too."},
        {"text": "Pack the folder `docs` into a compressed file `backup.tar.gz`. You should be standing in your home folder.",
         "hints": ["`tar -czf` creates a compressed archive file. First the name of the archive, then what to pack.", "Type `tar -czf backup.tar.gz docs`."],
         "sol": ["cd ~", "tar -czf backup.tar.gz docs"],
         "check": lambda g: isfile(g, "backup.tar.gz") and any(n.startswith("docs") for n in tarfile.open(g.P("backup.tar.gz")).getnames()), "xp": 20,
         "after": "The flags are c for create, z for gzip and f for file. Unpacking is `tar -xzf`. Now you never need to google it again."},
    ],
}

# ------------------------------------------------------------ level 10: the leak


def build10(g):
    r = random.Random(10)
    users = ["tnilsson", "mbergman", "akarlsson", "jekberg", "pwallin", "sholm"]
    ips = ["10.0.3.%d" % i for i in range(11, 21)]
    auth = []
    for _ in range(200):
        t = r.randint(6 * 3600, 23 * 3600 + 2700)
        if hms(t).startswith("23:47"):
            t += 120
        auth.append((t, "%s %s from %s" % (r.choice(["SSH-LOGIN", "SSH-LOGOUT", "SUDO"]), r.choice(users), r.choice(ips))))
    auth.append((85632, "SSH-LOGIN lfalk from 185.12.9.77"))
    auth.sort()
    W(g, "logs/auth.log", "\n".join("2026-09-28 %s %s" % (hms(t), m) for t, m in auth) + "\n")
    files = ["calendar.xlsx", "price_list.pdf", "org_chart.pptx", "contract_template.docx", "board_memo.pdf"]
    fa = []
    for _ in range(160):
        fa.append((r.randint(6 * 3600, 23 * 3600 + 3000), "%s %s %s" % (r.choice(users), r.choice(["READ", "COPY"]), r.choice(files))))
    fa.append((9 * 3600 + 730, "lfalk READ calendar.xlsx"))
    fa.append((85743, "lfalk COPY norrsken_plan.pdf -> /media/usb0"))
    fa.append((85900, "lfalk SEND norrsken_plan.pdf -> external"))
    fa.sort()
    W(g, "logs/fileaccess.log", "\n".join("2026-09-28 %s %s" % (hms(t), m) for t, m in fa) + "\n")
    for u in ["lfalk", "tnilsson", "mbergman"]:
        D(g, "homes/%s/.cache" % u)
        W(g, "homes/%s/docs/note.txt" % u, prose(r, 3))
    W(g, "homes/lfalk/.outbox/note.txt", "Sent via private email to erik@competitor-x.example.\nDelete this folder on Friday.\n")
    W(g, "homes/lfalk/docs/lunch.txt", "Friday: sushi.\n")
    spawn_spok(g)


L10 = {
    "title": "The leak",
    "story": ("It is Friday evening. You have tried everything: walked through folders, read logs, searched, piped, locked and scripted. "
              "GUS opens three things for you: `auth.log`, `fileaccess.log` and a folder with all the employees' home folders. "
              "\"Now you have every tool\", he says. \"Someone logged in after hours, copied the Norrsken plan and sent "
              "it on. Find out who, what and where. And shut down whatever is still running.\""),
    "learn": ("No new commands here. Everything you need, you have already learned. Use `hint` if you get stuck, "
              "but try first. Think: `grep`, `find`, `cat`, `ls -a`, `>`, `chmod` and `kill`."),
    "build": build10,
    "cheats": [("grep 23:47 logs/auth.log", "search a timestamp in a log"), ("find . -name \".*\" -type d", "find hidden folders")],
    "outro": "GUS: \"The report is written, locked and the process is stopped. That is more than many departments manage in a week.\"",
    "missions": [
        {"text": "The suspicious login happened at 23:47. Who logged in? Search `logs/auth.log` and answer with the username.",
         "hints": ["`grep` with the time as the search word.", "Type `grep 23:47 logs/auth.log`."],
         "sol": ["grep 23:47 logs/auth.log", ("svar", "lfalk")], "ans": "lfalk", "xp": 20,
         "after": "A single line among two hundred. You spotted it in under a second."},
        {"text": "Which file did that user copy? Search `logs/fileaccess.log` and answer with the file name.",
         "hints": ["Search for the username you found.", "Type `grep lfalk logs/fileaccess.log`."],
         "sol": ["grep lfalk logs/fileaccess.log", ("svar", "norrsken_plan.pdf")], "ans": "norrsken_plan.pdf", "xp": 20,
         "after": "Three lines, and one of them is the very file that leaked. It all fits together."},
        {"text": "The user had a hidden folder in their home folder, under `homes`. Find it, read the note and answer with the domain the file was sent to, for example `company.example`.",
         "hints": ["Hidden folders start with a dot. `find` with `-name` and `-type d` finds them.", "Type `find homes -name \".*\" -type d`. There is one that does not look like a cache. Read the file in it with `cat`."],
         "sol": ["find homes -name \".*\" -type d", "cat homes/lfalk/.outbox/note.txt", ("svar", "competitor-x.example")],
         "ans": ["competitor-x.example", "erik@competitor-x.example"], "xp": 25,
         "after": "You found what was hidden with `find`. Hidden in a file system is never invisible to someone who knows how to ask."},
        {"text": "Write the report. Create `report.txt` in your home folder that mentions the person's username, the file name and the domain. Make it readable only by you.",
         "hints": ["`echo` and `>` create the file. `chmod 600` locks it.", "Type `echo \"lfalk copied norrsken_plan.pdf and sent it to competitor-x.example\" > ~/report.txt` and then `chmod 600 ~/report.txt`."],
         "sol": ["echo \"lfalk copied norrsken_plan.pdf and sent it to competitor-x.example\" > ~/report.txt", "chmod 600 ~/report.txt"],
         "check": lambda g: isfile(g, "report.txt") and all(x in read(g, "report.txt").casefold() for x in ("lfalk", "norrsken_plan.pdf", "competitor-x.example"))
                            and (mode(g, "report.txt") & 0o077) == 0, "xp": 30,
         "after": "Evidence and permissions in the same mission. A report everyone can read is in practice a new leak."},
        {"text": "The process `spok` is still running and sending out data. Find it and shut it down.",
         "hints": ["You have done this. `pgrep` gives the PID, `kill` stops it.", "Type `kill $(pgrep spok)`."],
         "sol": ["kill $(pgrep spok)"], "check": lambda g: bool(g.procs) and g.procs[0].poll() is not None, "xp": 20,
         "after": "The leak is stopped. Everything you needed was in the terminal."},
    ],
}

EPILOGUE = (
    "GUS: \"Lena Falk had copied the plan to a USB stick and sent it to a competitor. Your report is with "
    "the boss. You walked in this morning with a prompt and a cup of coffee. Now you can navigate, read, build, search, chain "
    "commands, lock files, control processes and write your own scripts. Your terminal is also your own.\"\n\n"
    "GUS adds: \"That is enough to handle most of what you will run into. Keep typing. "
    "The terminal only gets better with use.\""
)

LEVELS = [L1, L2, L3, L4, L5, L6, L7, L8, L9, L10]
