# -*- coding: utf-8 -*-
"""Nivåer, uppdrag och världar för Terminalspelet.

Varje uppdrag har:
  text    vad spelaren ska åstadkomma
  hints   tips i stigande hjälpsamhet
  sol     lösning som kommandon, eller ("svar", värde)
  check   funktion som tittar på världen efter varje kommando, eller
  ans     rätt svar (text, lista eller funktion) för uppdrag som avgörs med `svar`
  xp      poäng
  after   vad man lärde sig
"""
import base64
import datetime
import os
import random
import re
import shutil
import stat
import subprocess
import tarfile
import time
from collections import Counter

# Skriptet som varje kommando körs i. Tillståndet (mapp, variabler, alias,
# funktioner, prompt) sparas mellan kommandona så att det känns som ett riktigt skal.
WRAP = r'''
shopt -s expand_aliases
set +H
__cmd="$TS_CMD"; __cwd="$TS_CWD"; __old="$TS_OLDPWD"; __st="$TS_STATE"
[ -f "$TS_STATE/env" ] && source "$TS_STATE/env" 2>/dev/null
[ -f "$TS_STATE/alias" ] && source "$TS_STATE/alias" 2>/dev/null
[ -f "$TS_STATE/funcs" ] && source "$TS_STATE/funcs" 2>/dev/null
[ -f "$TS_STATE/ps1" ] && PS1="$(cat "$TS_STATE/ps1")"
cd "$__cwd" 2>/dev/null
OLDPWD="$__old"
eval "$__cmd"
__ec=$?
pwd -P > "$__st/cwd"
echo "$OLDPWD" > "$__st/oldpwd"
export -p | grep -v -e ' TS_' -e ' __' > "$__st/env"
alias -p > "$__st/alias"
declare -f | sed -n '/^__/,/^}/!p' > "$__st/funcs"
printf '%s' "$PS1" > "$__st/ps1"
exit $__ec
'''

# ------------------------------------------------------------ hjälpare


def W(g, rel, text="", mode=None, binary=False):
    p = g.P(rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if binary:
        with open(p, "wb") as f:
            f.write(text)
    else:
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
    if mode is not None:
        os.chmod(p, mode)


def D(g, rel):
    os.makedirs(g.P(rel), exist_ok=True)


def isdir(g, rel):
    return os.path.isdir(g.P(rel))


def isfile(g, rel):
    return os.path.isfile(g.P(rel))


def read(g, rel):
    try:
        with open(g.P(rel), encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def mode(g, rel):
    return stat.S_IMODE(os.stat(g.P(rel)).st_mode)


def state(g, name):
    try:
        with open(os.path.join(g.state, name), encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def ran(g, pat, ok=True):
    return any(re.search(pat, e["cmd"]) and (e["ec"] == 0 or not ok) for e in g.mh)


def ranfail(g, pat):
    return any(re.search(pat, e["cmd"]) and e["ec"] != 0 for e in g.mh)


def lastcmd(g):
    return g.last["cmd"].strip() if g.last else ""


def walk_files(g):
    for d, _, fs in os.walk(g.root):
        for f in fs:
            yield os.path.join(d, f)


def walk_dirs(g):
    for d, ds, _ in os.walk(g.root):
        for x in ds:
            yield os.path.join(d, x)


def spawn_spok(g):
    dst = g.P("verktyg/spok")
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
    "Mötet öppnades klockan nio.", "Budgeten för nästa kvartal diskuterades.",
    "Leveransen från leverantören är försenad.", "Kaffemaskinen på tredje våningen ska bytas.",
    "Supporten rapporterade fler samtal än vanligt på måndagen.",
    "Ordföranden föreslog en uppföljning om två veckor.", "Ingen hade några synpunkter på dagordningen.",
    "Offerten godkändes utan ändringar.", "Kundundersökningen visade en liten förbättring.",
    "Nästa möte hålls i konferensrum Vega.", "Fakturorna för augusti är bokförda.",
    "Serverrummet behöver bättre kylning.", "Rekryteringen av en ny tekniker pausas till hösten.",
    "Rapporten skickas ut på fredag.", "Underhållsfönstret flyttades till söndag natt.",
]


def prose(r, n=None):
    n = n or r.randint(6, 12)
    return "\n".join(r.choice(SENT) for _ in range(n)) + "\n"


def hms(sec):
    return "%02d:%02d:%02d" % (sec // 3600, (sec % 3600) // 60, sec % 60)


# ------------------------------------------------------------ nivå 1: kartan

def build1(g):
    W(g, "välkommen.txt", "Välkommen till Fyrtornet AB.\nDin mapp är din. Ta det lugnt.\n")
    W(g, "kontor/reception/gästlista.txt", "Besökare idag: ingen ännu.\n")
    W(g, "kontor/kök/fikarum.txt", "Kaffekassan: 412 kr.\n")
    W(g, "kontor/serverrum/nod7.txt", "nod-7 uppe sedan 214 dagar.\n")
    D(g, "kontor/serverrum/rack_A")
    D(g, "kontor/serverrum/rack_B")
    D(g, "arkiv/2019")
    for q in range(1, 5):
        D(g, "arkiv/2020/q%d" % q)
    W(g, "arkiv/2020/q4/bokslut.txt", "Bokslut 2020, fjärde kvartalet.\n")


L1 = {
    "title": "Kartan",
    "story": ("Klockan är 07.12 en måndag. Du har fått ett passerkort, en kaffekopp och ett "
              "fönster där ingenting går att klicka på. Projekt Norrsken, Fyrtornets största lansering, "
              "har läckt till en konkurrent under natten. Någon måste gå igenom servern nod-7 och "
              "ta reda på hur. Den någon är du.\n\n"
              "GUS, systemets övervakare, hälsar dig välkommen: \"Här finns ingen mus. Det finns bara du "
              "och en prompt. Börja med att ta reda på var du står.\""),
    "learn": ("En terminal är ett textfönster där du styr datorn med kommandon i stället för att klicka. "
              "Filerna ligger i mappar, precis som i Finder. Skillnaden är att du alltid står på en plats, "
              "och den platsen kallas din nuvarande mapp.\n\n"
              "Tre kommandon räcker för att ta sig runt:\n"
              "- `pwd` visar var du står.\n"
              "- `ls` visar vad som finns där.\n"
              "- `cd mapp` går in i en mapp.\n\n"
              "Några genvägar: `..` betyder mappen ovanför, `~` är din hemmapp och `-` är platsen du nyss lämnade. "
              "Tryck Tab när du skrivit början på ett namn, så skriver terminalen klart det åt dig. "
              "Tab är det som gör terminalen snabbare än att klicka."),
    "build": build1,
    "cheats": [("pwd", "visa var du står"), ("ls", "lista innehållet i mappen"),
               ("cd mapp", "gå in i en mapp"), ("cd ..", "gå upp en nivå"),
               ("cd ~   (eller bara cd)", "gå hem"), ("cd -", "gå tillbaka dit du nyss var"),
               ("Tab", "skriv klart namnet åt mig")],
    "outro": "GUS: \"Du hittar runt. Det är mer än hälften av det hela. Nu ska vi läsa något.\"",
    "missions": [
        {"text": "Ta reda på var du står just nu.",
         "hints": ["Kommandot är tre bokstäver och står för print working directory.", "Skriv `pwd` och tryck Enter."],
         "sol": ["pwd"], "check": lambda g: ran(g, r"^\s*pwd\b"), "xp": 5,
         "after": "`pwd` skriver ut hela sökvägen till där du står. Sökvägen börjar med /, som är rotmappen på hela datorn."},
        {"text": "Lista vad som finns i mappen.",
         "hints": ["Kommandot heter som engelskans list, förkortat.", "Skriv `ls`."],
         "sol": ["ls"], "check": lambda g: ran(g, r"^\s*ls\b"), "xp": 5,
         "after": "`ls` visar filer och mappar. Mappar brukar ha en annan färg än filer."},
        {"text": "Gå in i mappen `kontor`.",
         "hints": ["`cd` betyder change directory. Efter det skriver du mappens namn.", "Skriv `cd kontor`."],
         "sol": ["cd kontor"], "check": lambda g: g.cwd == g.P("kontor"), "xp": 5,
         "after": "Stavar du fel får du ett felmeddelande, och du blir stående där du är. Inget går sönder av det."},
        {"text": "Ta dig vidare in i `serverrum`. Skriv `cd ser` och tryck Tab i stället för att skriva resten.",
         "hints": ["Skriv bara `cd ser` och tryck sedan Tab-tangenten.", "Skriv `cd serverrum`."],
         "sol": ["cd serverrum"], "check": lambda g: g.cwd == g.P("kontor/serverrum"), "xp": 10,
         "after": "Tab fyller i det som är entydigt. Finns flera träffar visar dubbel-Tab alla. Vana terminalanvändare skriver nästan aldrig ett helt filnamn."},
        {"text": "Backa en nivå upp, till `kontor`.",
         "hints": ["Två punkter betyder mappen ovanför.", "Skriv `cd ..`"],
         "sol": ["cd .."], "check": lambda g: re.match(r"^cd\s+\.\./?$", lastcmd(g)) and g.cwd == g.P("kontor"), "xp": 5,
         "after": "`..` fungerar överallt. `cd ../..` tar dig två steg upp, och `ls ..` listar mappen ovanför utan att du flyttar dig."},
        {"text": "Gå hem, till din hemmapp, med ett kort kommando.",
         "hints": ["Hemmappen har en egen symbol: en tilde.", "Skriv `cd ~`. Bara `cd` utan något efter fungerar också."],
         "sol": ["cd ~"], "check": lambda g: g.cwd == g.root and lastcmd(g).startswith("cd"), "xp": 5,
         "after": "`~` är alltid din hemmapp, oavsett var du står. Det är den snabbaste vägen tillbaka när du har gått vilse."},
        {"text": "Arkivet ligger i `arkiv/2020/q4`. Ta dig dit med ett enda `cd`-kommando.",
         "hints": ["Du kan skriva hela vägen på en gång, med snedstreck mellan mapparna.", "Skriv `cd arkiv/2020/q4`. Med Tab går det fort."],
         "sol": ["cd arkiv/2020/q4"], "check": lambda g: g.cwd == g.P("arkiv/2020/q4"), "xp": 10,
         "after": "En sökväg som `arkiv/2020/q4` kallas relativ, eftersom den utgår från där du står. En som börjar med / kallas absolut."},
        {"text": "Hoppa hem, och ta dig sedan tillbaka till `q4` med ett kort kommando som minns var du var.",
         "hints": ["Minustecknet betyder föregående plats.", "Skriv `cd ~` och sedan `cd -`."],
         "sol": ["cd ~", "cd -"],
         "check": lambda g: lastcmd(g) == "cd -" and g.cwd == g.P("arkiv/2020/q4") and any(re.match(r"^cd(\s+~/?)?$", e["cmd"].strip()) for e in g.mh),
         "xp": 10,
         "after": "`cd -` är som bakåtknappen i en webbläsare. Nyttigt när du hoppar mellan två mappar som ligger långt ifrån varandra."},
        {"text": "Hur många mappar ligger direkt i `kontor`? Titta med `ls` och svara.",
         "hints": ["Du behöver inte gå dit. `ls kontor` listar den mappen från där du står.", "Skriv `ls kontor` och räkna. Svara sedan med `svar 3`, om det är tre."],
         "sol": ["ls kontor", ("svar", "3")], "ans": "3", "xp": 10,
         "after": "`ls` går att peka på en annan mapp. De flesta kommandon fungerar så: kommandot, sedan vad det ska göra det med."},
    ],
}

# ------------------------------------------------------------ nivå 2: läsa


def build2(g):
    r = random.Random(2 * 1000003 + g.seed)
    W(g, "meddelande.txt",
      "Till: ny agent\nFrån: GUS\n\nVälkommen ombord. Projekt Norrsken har läckt.\n"
      "Jag har lagt loggar, rapporter och bilagor i din hemmapp.\n"
      "Det mesta ligger synligt. Allt ligger inte det.\n\n/GUS\n")
    W(g, ".anteckning_gömd", "Reservlösenord till arkivet: UGGLA42\nRadera den här innan chefen ser den.\n")
    users = ["akarlsson", "mbergman", "jekberg", "pwallin", "sholm", "cdahl", "okarlsson"]
    msgs = ["INFO  session öppnad för användare: %s", "INFO  backup slutförd (%d filer)",
            "WARN  diskutrymme under 20 procent på /data", "INFO  tjänsten mailrelay omstartad",
            "INFO  certifikat förnyat för intern.fyrtornet.example", "WARN  långsam fråga mot databasen (%d ms)"]
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
    lines.append("2026-09-28 23:58:41 INFO  session öppnad för användare: tnilsson")
    W(g, "loggar/serverlogg.log", "\n".join(lines) + "\n")
    g.S["loglines"] = str(len(lines))
    W(g, "rapporter/q1.txt", prose(r, 7))
    W(g, "rapporter/q2.txt", prose(r, 60))
    W(g, "rapporter/q3.txt", prose(r, 800))
    W(g, "rapporter/sammanfattning.txt", prose(r, 20))
    W(g, "bilagor/foto", base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="),
      binary=True)
    W(g, "bilagor/kontakter.txt", "växel 08-555 01 00\n")


L2 = {
    "title": "Läs som en detektiv",
    "story": ("GUS har gett dig läsrätt till loggarna på nod-7. Det finns ingen nyckelbild och ingen tidslinje, "
              "bara textfiler. Vill du hitta något får du läsa. Som tur är kan terminalen läsa åt dig på flera sätt, "
              "och inget av det ändrar en enda fil."),
    "learn": ("Innan du ändrar något ska du läsa. Kommandona här är ofarliga. De kan inte förstöra något.\n"
              "- `cat fil` skriver ut hela filen.\n"
              "- `head fil` visar början och `tail fil` slutet. Med `-n 5` väljer du hur många rader.\n"
              "- `less fil` öppnar en bläddrare. Pilarna rullar, mellanslag tar en sida och `q` avslutar.\n"
              "- `wc -l fil` räknar rader.\n"
              "- `file fil` berättar vad en fil egentligen är, oavsett vad den heter.\n"
              "- `ls -l` visar storlek och rättigheter, `ls -a` visar dolda filer (de som börjar med punkt) "
              "och `ls -S` sorterar på storlek.\n\n"
              "Flaggor som `-l` och `-a` går att slå ihop: `ls -la`."),
    "build": build2,
    "cheats": [("cat fil", "skriv ut hela filen"), ("head -n 5 fil", "visa de första fem raderna"),
               ("tail -n 5 fil", "visa de sista fem raderna"), ("less fil", "bläddra i en fil (q avslutar)"),
               ("wc -l fil", "räkna rader"), ("file fil", "ta reda på vad en fil är"),
               ("ls -la", "lista allt, även dolt, med detaljer"), ("ls -lS", "sortera efter storlek"),
               ("ls -lh", "visa storlekar läsbart")],
    "outro": "GUS: \"En bra detektiv läser först och rör sedan. Du börjar likna en.\"",
    "missions": [
        {"text": "Läs GUS meddelande i `meddelande.txt`.",
         "hints": ["Kommandot som skriver ut en hel fil heter som en djurart.", "Skriv `cat meddelande.txt`."],
         "sol": ["cat meddelande.txt"], "check": lambda g: ran(g, r"\bcat\b.*meddelande"), "xp": 5,
         "after": "`cat` skriver ut en fils innehåll. Namnet kommer av concatenate, sammanfoga, men mest används det för att läsa."},
        {"text": "GUS säger att inte allt ligger synligt. Visa också de dolda filerna i mappen.",
         "hints": ["Filer som börjar med en punkt är dolda. En flagga till `ls` visar dem.", "Skriv `ls -a`."],
         "sol": ["ls -a"], "check": lambda g: ran(g, r"\bls\b.*\s-\w*a"), "xp": 10,
         "after": "Dolda filer heter något som börjar med punkt. Din Mac är full av dem, till exempel `.zshrc`. Vi kommer tillbaka till den."},
        {"text": "Läs den dolda filen. Vad är reservlösenordet? Svara med `svar <lösenordet>`.",
         "hints": ["Det är bara `cat` igen, men med ett namn som börjar på punkt. Tab hjälper.", "Skriv `cat .anteckning_gömd`."],
         "sol": ["cat .anteckning_gömd", ("svar", "UGGLA42")], "ans": "UGGLA42", "xp": 10,
         "after": "Dold betyder inte hemlig. Den som skriver `ls -a` ser allt. Lägg aldrig lösenord i en fil bara för att den är dold."},
        {"text": "Titta på de tre första raderna i `loggar/serverlogg.log`.",
         "hints": ["`head` visar början av en fil. Med `-n` väljer du hur många rader.", "Skriv `head -n 3 loggar/serverlogg.log`."],
         "sol": ["head -n 3 loggar/serverlogg.log"], "check": lambda g: ran(g, r"\bhead\b.*serverlogg"), "xp": 10,
         "after": "Loggar är långa. `head` och `tail` låter dig kika på ändarna utan att fylla skärmen."},
        {"text": "Vem var senast inloggad? Titta på slutet av loggen och svara med användarnamnet.",
         "hints": ["`tail` är syskon till `head`, men för slutet.", "Skriv `tail loggar/serverlogg.log`. Sista raden nämner en användare."],
         "sol": ["tail loggar/serverlogg.log", ("svar", "tnilsson")], "ans": "tnilsson", "xp": 10,
         "after": "`tail` är mest känd för `tail -f`, som följer en logg live medan den växer. Kolla det någon gång på en riktig server."},
        {"text": "Hur många rader har `loggar/serverlogg.log`? Låt terminalen räkna åt dig och svara med talet.",
         "hints": ["`wc` står för word count. En flagga gör att den räknar rader i stället för ord.", "Skriv `wc -l loggar/serverlogg.log`."],
         "sol": ["wc -l loggar/serverlogg.log", ("svar", lambda g: g.S["loglines"])], "ans": lambda g: g.S["loglines"], "xp": 10,
         "after": "`wc -l` är ett av de vanligaste kommandona som finns. Det får sin verkliga kraft i nästa nivå, när du kopplar ihop det med andra."},
        {"text": "Vilken fil i `rapporter` är störst? Sortera efter storlek och svara med filnamnet.",
         "hints": ["`ls -l` visar storlek. En extra flagga sorterar med den största först.", "Skriv `ls -lS rapporter`. Lägg till `h` för läsbara storlekar."],
         "sol": ["ls -lS rapporter", ("svar", "q3.txt")], "ans": "q3.txt", "xp": 10,
         "after": "Flaggor kan kombineras: `ls -lSh` ger lång lista, sorterad på storlek, med läsbara enheter. Ordningen på bokstäverna spelar sällan roll."},
        {"text": "Filen `bilagor/foto` har ingen ändelse. Vad är det för sorts fil? Svara med filtypen, ett ord.",
         "hints": ["Det finns ett kommando som tittar på innehållet i stället för på namnet.", "Skriv `file bilagor/foto`. Svara med det första ordet i beskrivningen."],
         "sol": ["file bilagor/foto", ("svar", "PNG")], "ans": ["png", "PNG image data"], "xp": 10,
         "after": "Filändelsen är bara en konvention. `file` läser de första byten och vet. Bra när ett mejl innehåller en misstänkt bilaga."},
        {"text": "Öppna hela loggen med `less` och bläddra lite. Avsluta med `q`.",
         "hints": ["`less` öppnar en fil du kan rulla i.", "Skriv `less loggar/serverlogg.log`, rulla med pilarna, tryck `q`."],
         "sol": ["less loggar/serverlogg.log"], "check": lambda g: ran(g, r"\bless\b"), "xp": 10,
         "after": "I `less` kan du söka: skriv `/` och ett ord, sedan Enter. `n` hoppar till nästa träff. Precis som Cmd+F fast för en 100 MB stor fil."},
    ],
}

# ------------------------------------------------------------ nivå 3: bygga


def build3(g):
    r = random.Random(3 * 1000003 + g.seed)
    W(g, "skrivbord/rapport_utkast.txt", "Utkast, ej klart.\n")
    W(g, "skrivbord/kvitto.txt", "Kvitto 2026-09-14: kaffebönor, 389 kr.\n")
    W(g, "skrivbord/slarv.txt", "Jag skulle ju flytta den här.\n")
    W(g, "skrivbord/bild1.png", "inte en bild på riktigt\n")
    for n in "abcde":
        W(g, "skrivbord/%s.tmp" % n, "tillfällig fil\n")
    W(g, "skrivbord/gammalt/kopia1.txt", "gammalt\n")
    W(g, "skrivbord/gammalt/kopia2.txt", "gammalt\n")


L3 = {
    "title": "Bygg, flytta, städa",
    "story": ("Du har läst klart. Nu behöver du en plats för bevisen. GUS har lämnat ett rörigt skrivbord åt dig: "
              "en handfull temporära filer, en mapp med gamla kopior och ett par filer som ligger fel. "
              "\"Ordning i mappen, ordning i huvudet\", säger han."),
    "learn": ("Nu ändrar du saker på riktigt.\n"
              "- `mkdir namn` skapar en mapp. Med `-p` skapar den flera nivåer i ett svep.\n"
              "- `touch fil` skapar en tom fil.\n"
              "- `cp från till` kopierar. `mv från till` flyttar, och byter namn på samma sätt.\n"
              "- `rm fil` tar bort. Med `-r` tar den bort en hel mapp med innehåll.\n"
              "- `echo text > fil` skriver text till en fil. `>>` lägger till i stället för att skriva över.\n"
              "- `*` fungerar som joker: `*.tmp` betyder alla filer som slutar på .tmp.\n\n"
              "Varning: `rm` har ingen papperskorg. Det som är borta är borta, och det gäller på din riktiga dator också. "
              "Här kan `:reset` bygga om världen, men vänj dig vid att titta med `ls` innan du raderar."),
    "build": build3,
    "cheats": [("mkdir namn", "skapa en mapp"), ("mkdir -p a/b/c", "skapa flera nivåer på en gång"),
               ("touch fil", "skapa en tom fil"), ("cp från till", "kopiera"),
               ("mv från till", "flytta eller döp om"), ("rm fil", "ta bort en fil, ingen ångra"),
               ("rm -r mapp", "ta bort en mapp med innehåll"), ("echo text > fil", "skriv text till fil (skriver över)"),
               ("echo text >> fil", "lägg till text sist i fil"), ("*.tmp", "joker: alla som slutar på .tmp")],
    "outro": "GUS: \"Bevismappen är ordnad och skrivbordet städat. Snart vill jag inte ha dig ifrån terminalen.\"",
    "missions": [
        {"text": "Skapa en mapp som heter `bevis` i din hemmapp.",
         "hints": ["Kommandot är make directory, förkortat.", "Skriv `mkdir bevis`."],
         "sol": ["mkdir bevis"], "check": lambda g: isdir(g, "bevis"), "xp": 5,
         "after": "`mkdir` skapar mappar. Finns den redan säger terminalen ifrån och rör ingenting."},
        {"text": "Skapa en tom fil `anteckningar.txt` inuti `bevis`, utan att gå dit.",
         "hints": ["`touch` skapar en tom fil om den inte finns.", "Skriv `touch bevis/anteckningar.txt`."],
         "sol": ["touch bevis/anteckningar.txt"], "check": lambda g: isfile(g, "bevis/anteckningar.txt"), "xp": 5,
         "after": "Du behöver inte stå i mappen. Ge kommandot hela sökvägen så hittar det rätt."},
        {"text": "Kopiera `skrivbord/kvitto.txt` in i `bevis`. Originalet ska ligga kvar.",
         "hints": ["`cp` tar två saker: vad som ska kopieras och vart.", "Skriv `cp skrivbord/kvitto.txt bevis/`."],
         "sol": ["cp skrivbord/kvitto.txt bevis/"], "check": lambda g: isfile(g, "bevis/kvitto.txt") and isfile(g, "skrivbord/kvitto.txt"), "xp": 10,
         "after": "`cp` gör en kopia, `mv` flyttar originalet. Den enda skillnaden är om något blir kvar på gamla platsen."},
        {"text": "Flytta `skrivbord/slarv.txt` till `bevis` och döp samtidigt om den till `hemligt.txt`.",
         "hints": ["`mv` flyttar. Är målet ett nytt filnamn döps filen om på samma gång.", "Skriv `mv skrivbord/slarv.txt bevis/hemligt.txt`."],
         "sol": ["mv skrivbord/slarv.txt bevis/hemligt.txt"], "check": lambda g: isfile(g, "bevis/hemligt.txt") and not isfile(g, "skrivbord/slarv.txt"), "xp": 10,
         "after": "Det finns inget eget kommando för att byta namn. `mv gammalt nytt` gör det."},
        {"text": "Skriv en rad text till `bevis/logg.txt` med `echo` och `>`.",
         "hints": ["`>` skickar utskriften från ett kommando in i en fil i stället för till skärmen.", "Skriv `echo \"Bevis samlade\" > bevis/logg.txt`."],
         "sol": ["echo \"Bevis samlade\" > bevis/logg.txt"], "check": lambda g: len(read(g, "bevis/logg.txt").strip()) > 0 and ran(g, r">"), "xp": 10,
         "after": "`>` skriver över allt som fanns. Skriver du den till en fil med innehåll försvinner det. Nästa uppdrag visar hur du undviker det."},
        {"text": "Lägg till en rad till i `bevis/logg.txt` utan att radera den första. Filen ska ha minst två rader.",
         "hints": ["Två pilar i rad lägger till på slutet.", "Skriv `echo \"Rad två\" >> bevis/logg.txt`."],
         "sol": ["echo \"Rad två\" >> bevis/logg.txt"],
         "check": lambda g: len(read(g, "bevis/logg.txt").strip().splitlines()) >= 2 and ran(g, r">>"), "xp": 10,
         "after": "`>` skriver över, `>>` lägger till. Den skillnaden är källan till många förlorade loggfiler."},
        {"text": "Ta bort alla `.tmp`-filer i `skrivbord` med ett enda kommando. De andra filerna ska vara kvar.",
         "hints": ["Med jokertecknet `*` kan du peka ut alla som slutar på samma sätt.", "Skriv `rm skrivbord/*.tmp`."],
         "sol": ["rm skrivbord/*.tmp"],
         "check": lambda g: not [f for f in os.listdir(g.P("skrivbord")) if f.endswith(".tmp")] and isfile(g, "skrivbord/rapport_utkast.txt") and isfile(g, "skrivbord/bild1.png"), "xp": 15,
         "after": "Skalet byter ut `*.tmp` mot alla träffande filnamn innan `rm` startar. Kör `ls skrivbord/*.tmp` först om du vill se vad som kommer försvinna."},
        {"text": "Ta bort hela mappen `skrivbord/gammalt` med allt i.",
         "hints": ["`rm` vägrar ta mappar om du inte säger att det är ok. Flaggan `-r` betyder rekursivt.", "Skriv `rm -r skrivbord/gammalt`."],
         "sol": ["rm -r skrivbord/gammalt"], "check": lambda g: not isdir(g, "skrivbord/gammalt"), "xp": 10,
         "after": "`rm -r` följer med ner i alla undermappar. Aldrig `rm -rf` på en sökväg du inte har läst igenom. `-f` betyder fråga inte."},
        {"text": "Skapa mappstrukturen `projekt/norrsken/design/mockups` med ett enda kommando.",
         "hints": ["Utan flagga misslyckas `mkdir` om mellanmapparna saknas. Det finns en flagga som skapar dem.", "Skriv `mkdir -p projekt/norrsken/design/mockups`."],
         "sol": ["mkdir -p projekt/norrsken/design/mockups"], "check": lambda g: isdir(g, "projekt/norrsken/design/mockups"), "xp": 10,
         "after": "`-p` står för parents. Hela kedjan skapas, och om den redan finns är det inget fel. Bra att ha i skript."},
    ],
}

# ------------------------------------------------------------ nivå 4: spåra


def build4(g):
    r = random.Random(4 * 1000003 + g.seed)
    sw = lambda n: prose(r, n)
    W(g, "arkiv/2022/semester/resa.txt", sw(5) + "Vi såg norrsken i Abisko, det var fint.\n")
    W(g, "arkiv/2022/ekonomi/budget.txt", sw(9))
    W(g, "arkiv/2023/backup.log", "INFO backup ok\nINFO backup ok\nWARN långsam disk\n")
    W(g, "arkiv/2023/hemligt_projekt/plan_b.txt", sw(6))
    W(g, "arkiv/2023/marknad/kampanj.txt", sw(8))
    W(g, "arkiv/2024/marknad/ideer.txt", sw(4) + "Kampanjbild: ljuset från norrsken.\n")
    W(g, "arkiv/2024/it/inventarie.txt", sw(9))
    W(g, "arkiv/2024/stor_backup.bin", b"0" * 300000, binary=True)
    W(g, "arkiv/2025/hr/protokoll_okt.txt", sw(5) + "Punkt 4: Projekt Norrsken, sekretess gäller.\n" + sw(3))
    W(g, "arkiv/2025/hr/rekrytering.txt", sw(7))
    W(g, "arkiv/2025/styrelse/styrelsemote.txt", sw(4) + "Lanseringen av Norrsken sker den 19 oktober.\n" + sw(4))
    W(g, "arkiv/2025/it/incidenter.txt", sw(10))
    W(g, "notiser.md", "# Notiser\n" + sw(5))
    W(g, "kontor/serverrum/nod7.log", "INFO nod-7 startad\n")
    for y, seed in (("2024", 41), ("2025", 42)):
        rr = random.Random(seed * 1000003 + g.seed)
        msgs = ["INFO  tjänst startad", "INFO  anslutning från 10.0.3.%d", "WARN  hög minnesanvändning",
                "INFO  cache rensad", "ERROR anslutning nekad från 10.0.3.%d", "ERROR timeout mot databasen"]
        lines = []
        for i in range(120):
            m = rr.choice(msgs)
            if "%d" in m:
                m = m % rr.randint(11, 40)
            lines.append(m)
        if y == "2025":
            k = rr.randint(60, 95)
            lines[k] = "KRITISKT: databasen svarar inte"
            g.S["kritiskt"] = str(k + 1)
            g.S["errors"] = str(sum(1 for x in lines if "ERROR" in x))
        W(g, "arkiv/%s/system.log" % y, "\n".join(lines) + "\n")
    g.S["logs"] = str(sum(1 for p in [q for q in _files(g)] if p.endswith(".log")))


def _files(g):
    return list(walk_files(g))


L4 = {
    "title": "Spårhunden",
    "story": ("Arkivet innehåller tusentals rader text från fyra år. Någonstans i den högen finns spåren efter "
              "läckan, och du har inte tid att öppna varje fil. \"Man hittar inte nålen genom att titta på höet\", "
              "säger GUS. \"Man ber terminalen leta åt en.\""),
    "learn": ("Två kommandon gör det mesta av sökandet:\n"
              "- `find var -name \"*.log\"` letar efter filer på namn. Varianter: `-type d` bara mappar, "
              "`-size +100k` bara stora filer.\n"
              "- `grep ord fil` visar rader som innehåller ett ord. `-r` letar i en hel mapp, `-i` struntar i "
              "stora och små bokstäver, `-c` räknar träffar, `-n` visar radnummer och `-l` visar bara filnamnen.\n\n"
              "`.` betyder här, alltså den mapp du står i. `find . -name x` letar från där du står.\n"
              "Sätt citattecken runt mönster med joker, som `\"*.log\"`, så att det är find som tolkar det och inte skalet."),
    "build": build4,
    "cheats": [("find . -name \"*.log\"", "hitta filer på namn"), ("find . -type d", "hitta bara mappar"),
               ("find . -size +100k", "hitta stora filer"), ("grep ord fil", "visa rader med ord"),
               ("grep -r ord .", "sök i alla filer under mappen"), ("grep -i", "ignorera stora/små bokstäver"),
               ("grep -c / -n / -l", "räkna / radnummer / bara filnamn")],
    "outro": "GUS: \"Nålen är hittad. Nästa gång låter du terminalen göra jobbet innan du börjar bläddra.\"",
    "missions": [
        {"text": "Hur många filer som slutar på `.log` finns i hela hemmappen? Svara med antalet.",
         "hints": ["`find` letar. Först var den ska leta, sedan `-name` och mönstret.", "Skriv `find . -name \"*.log\"` och räkna raderna."],
         "sol": ["find . -name \"*.log\"", ("svar", lambda g: g.S["logs"])], "ans": lambda g: g.S["logs"], "xp": 10,
         "after": "`find` går igenom alla undermappar av sig själv. Mönstret ska stå inom citattecken, annars kan skalet peta på det."},
        {"text": "Det finns en mapp vars namn börjar på `hemlig`. Vad heter den? Svara med mappens namn.",
         "hints": ["`find` kan begränsa sig till mappar med `-type d`. Kombinera med `-name`.", "Skriv `find . -type d -name \"hemlig*\"`."],
         "sol": ["find . -type d -name \"hemlig*\"", ("svar", "hemligt_projekt")], "ans": "hemligt_projekt", "xp": 10,
         "after": "`*` betyder vad som helst. Du behövde bara veta början av namnet."},
        {"text": "Hur många filer nämner ordet `Norrsken` exakt så, med stort N? Svara med antalet.",
         "hints": ["`grep -r` letar igenom en hel mapp. Lägg till `-l` så får du bara filnamnen, och räkna dem.", "Skriv `grep -rl Norrsken .`"],
         "sol": ["grep -rl Norrsken .", ("svar", "2")], "ans": "2", "xp": 15,
         "after": "`grep` skiljer på stora och små bokstäver om du inte säger annat. Nästa uppdrag visar hur du släpper det."},
        {"text": "Räkna nu igen, men ta med alla stavningar oavsett stora och små bokstäver. Hur många filer?",
         "hints": ["En flagga gör `grep` okänslig för versaler.", "Skriv `grep -rli norrsken .` och räkna raderna."],
         "sol": ["grep -rli norrsken .", ("svar", "4")], "ans": "4", "xp": 15,
         "after": "Två av träffarna handlar bara om norrskenet på himlen. En bra sökning kräver att du läser resultaten, inte bara räknar dem."},
        {"text": "Hur många rader innehåller ordet `ERROR` i `arkiv/2025/system.log`? Svara med antalet.",
         "hints": ["`grep` kan räkna träffande rader åt dig med en flagga.", "Skriv `grep -c ERROR arkiv/2025/system.log`."],
         "sol": ["grep -c ERROR arkiv/2025/system.log", ("svar", lambda g: g.S["errors"])], "ans": lambda g: g.S["errors"], "xp": 10,
         "after": "`-c` räknar rader med träff. Har en rad ordet två gånger räknas den ändå bara en gång."},
        {"text": "På vilken rad i `arkiv/2025/system.log` står det `KRITISKT`? Svara med radnumret.",
         "hints": ["En flagga skriver ut radnummer framför varje träff.", "Skriv `grep -n KRITISKT arkiv/2025/system.log`."],
         "sol": ["grep -n KRITISKT arkiv/2025/system.log", ("svar", lambda g: g.S["kritiskt"])], "ans": lambda g: g.S["kritiskt"], "xp": 10,
         "after": "`-n` ger radnummer. Praktiskt när du vill öppna filen i en editor och hoppa rakt dit."},
        {"text": "En fil i arkivet tar upp orimligt mycket plats. Hitta den som är större än 100 kilobyte och svara med filnamnet.",
         "hints": ["`find` kan filtrera på storlek. Plus betyder större än, och `k` betyder kilobyte.", "Skriv `find . -size +100k`."],
         "sol": ["find . -size +100k", ("svar", "stor_backup.bin")], "ans": "stor_backup.bin", "xp": 15,
         "after": "`find . -size +100M` är något du kommer köra när disken är full och du undrar varför."},
    ],
}

# ------------------------------------------------------------ nivå 5: rör


def build5(g):
    seed = 50
    while True:
        r = random.Random(seed * 1000003 + g.seed)
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
    W(g, "loggar/access.log", "\n".join(lines) + "\n")
    g.S.update(nlines=str(len(lines)), topip=ipc[0][0], top3=[x[0] for x in ipc[:3]],
               nfailed=sum(1 for x in ev if x[3] == "LOGIN_FAILED"), topfail=failc[0][0])
    people = ([("Drift", 42000)] * 7 + [("Marknad", 39000)] * 5 + [("Ekonomi", 44000)] * 4
              + [("Support", 36000)] * 3 + [("Ledning", 65000)] * 2)
    names = ["Tomas Nilsson", "Maria Bergman", "Anders Karlsson", "Johanna Ekberg", "Per Wallin", "Sara Holm",
             "Olof Karlsson", "Cecilia Dahl", "Lena Falk", "Karin Lund", "Nils Persson", "Eva Sjö", "Johan Berg",
             "Ida Öberg", "Rasmus Ek", "Mia Hedlund", "Ola Ström", "Anna Viklund", "Hugo Mård", "Elin Nord",
             "Kurt Gran"]
    rows = ["namn,avdelning,lön"]
    for n, (d, s) in zip(names, people):
        rows.append("%s,%s,%d" % (n, d, s + r.randint(0, 20) * 100))
    W(g, "personal.csv", "\n".join(rows) + "\n")
    g.S["topdept"] = "Drift"


L5 = {
    "title": "Rör och pipes",
    "story": ("Nu har du en åtkomstlogg med 360 rader. Ingen människa läser den, men terminalen kan. "
              "Hemligheten är att kommandon går att koppla ihop: utskriften från ett blir indata till nästa. "
              "\"Det heter pipe\", säger GUS. \"Tänk Lego. Varje kommando gör en liten sak. Tillsammans gör de vad som helst.\""),
    "learn": ("Två verktyg gör terminalen kraftfull:\n"
              "- `|` (pipe, tecknet finns på Alt+7) skickar utskriften från vänster kommando in i höger kommando.\n"
              "- `>` skickar utskriften till en fil i stället för till skärmen. `>>` lägger till.\n\n"
              "Byggstenarna du kopplar ihop:\n"
              "- `sort` sorterar rader. `sort -rn` sorterar talen störst först.\n"
              "- `uniq -c` slår ihop lika rader bredvid varandra och räknar dem. Sortera alltid först.\n"
              "- `cut -d' ' -f3` plockar kolumn 3 om kolumnerna skiljs av mellanslag. `-d,` för komma.\n"
              "- `head -n 3` behåller de tre första raderna.\n\n"
              "Mönstret \"räkna vilka som förekommer mest\" är: `... | sort | uniq -c | sort -rn | head`. "
              "Du kommer använda det hela livet."),
    "build": build5,
    "cheats": [("kommando1 | kommando2", "koppla ihop: utskrift blir indata"), ("kommando > fil", "spara utskriften i fil"),
               ("sort / sort -rn", "sortera / sortera tal, störst först"), ("uniq -c", "räkna lika rader (sortera först)"),
               ("cut -d' ' -f3", "plocka kolumn 3, delat på mellanslag"), ("cut -d, -f2", "plocka kolumn 2 i en csv"),
               ("... | sort | uniq -c | sort -rn | head", "topplista över vad som förekommer mest")],
    "outro": "GUS: \"Vi vet nu vem som hamrade på dörren. Mönstret för sådana listor kan du på ryggraden nu.\"",
    "missions": [
        {"text": "Räkna raderna i `loggar/access.log`, men den här gången med ett rör: skicka filen genom `cat` in i `wc -l`.",
         "hints": ["Skriv kommandot som läser filen, sedan tecknet `|`, sedan kommandot som räknar.", "Skriv `cat loggar/access.log | wc -l`."],
         "sol": ["cat loggar/access.log | wc -l"], "check": lambda g: ran(g, r"\|\s*wc"), "xp": 10,
         "after": "Så här ser en pipe ut. `cat` skriver ut, `|` skickar vidare, `wc` räknar. Varje verktyg gör en sak."},
        {"text": "Vilken IP-adress förekommer flest gånger i loggen? Kolumn 3 är IP-adressen. Svara med adressen.",
         "hints": ["Plocka kolumn 3, sortera, räkna lika, sortera på antal, ta översta raden.", "Skriv `cut -d' ' -f3 loggar/access.log | sort | uniq -c | sort -rn | head -1`."],
         "sol": ["cut -d' ' -f3 loggar/access.log | sort | uniq -c | sort -rn | head -1", ("svar", lambda g: g.S["topip"])],
         "ans": lambda g: g.S["topip"], "xp": 20,
         "after": "Det där är den klassiska toppen-listan. Fyra små kommandon, och du har svaret på något som skulle tagit en kvart i ett kalkylark."},
        {"text": "Spara alla rader med `FAILED` i en ny fil `misslyckade.txt`.",
         "hints": ["`grep` hittar raderna. `>` skickar resultatet till en fil.", "Skriv `grep FAILED loggar/access.log > misslyckade.txt`."],
         "sol": ["grep FAILED loggar/access.log > misslyckade.txt"],
         "check": lambda g: len(read(g, "misslyckade.txt").strip().splitlines()) == g.S["nfailed"] and ran(g, r">"), "xp": 15,
         "after": "Nu har du en fil att skicka vidare, eller jobba mer med. Det som är svårt att göra i ett gränssnitt är trivialt här."},
        {"text": "Vilken användare har flest misslyckade inloggningar? Användarnamnet står i kolumn 4. Svara med namnet.",
         "hints": ["Börja med `grep FAILED`, plocka kolumn 4, och sedan samma topplista som förut.", "Skriv `grep FAILED loggar/access.log | cut -d' ' -f4 | sort | uniq -c | sort -rn | head -1`."],
         "sol": ["grep FAILED loggar/access.log | cut -d' ' -f4 | sort | uniq -c | sort -rn | head -1", ("svar", lambda g: g.S["topfail"])],
         "ans": lambda g: g.S["topfail"], "xp": 20,
         "after": "Sex kommandon i rad, och du har ett namn. Notera det. Någon försökte komma in mycket hårdare än alla andra."},
        {"text": "I `personal.csv` är avdelning kolumn 2, med komma som avskiljare. Vilken avdelning har flest anställda? Svara med namnet.",
         "hints": ["`cut` har en flagga för avskiljare, `-d,`. Sedan samma topplista.", "Skriv `cut -d, -f2 personal.csv | sort | uniq -c | sort -rn | head -3`."],
         "sol": ["cut -d, -f2 personal.csv | sort | uniq -c | sort -rn | head -3", ("svar", "Drift")], "ans": "Drift", "xp": 15,
         "after": "Samma mönster fungerar på vilken kolumn som helst, i vilken fil som helst. Prova det på en export ur ett system du jobbar med."},
        {"text": "Spara de tre vanligaste IP-adresserna, med antal, i en fil `toppip.txt`.",
         "hints": ["Du har redan listan från uppdrag 2. Låt den ge tre rader i stället för en och skicka den till en fil.", "Skriv `cut -d' ' -f3 loggar/access.log | sort | uniq -c | sort -rn | head -3 > toppip.txt`."],
         "sol": ["cut -d' ' -f3 loggar/access.log | sort | uniq -c | sort -rn | head -3 > toppip.txt"],
         "check": lambda g: (lambda ls: len(ls) == 3 and set(l.split()[-1] for l in ls) == set(g.S["top3"]))(read(g, "toppip.txt").strip().splitlines()),
         "xp": 20,
         "after": "Du har byggt din första riktiga pipeline. Den går att spara som ett alias eller skript, och det gör vi längre fram."},
    ],
}

# ------------------------------------------------------------ nivå 6: rättigheter


def build6(g):
    W(g, "verktyg/avkoda.sh",
      '#!/bin/bash\necho "Avkodar signal från nod-7..."\necho "KOD: $(rev < "$(dirname "$0")/signal.txt")"\n',
      mode=0o644)
    W(g, "verktyg/signal.txt", "YLFNOGROM\n")
    W(g, "hemlig.nyckel", "nyckeln till serverrummet\n", mode=0o777)


L6 = {
    "title": "Rättigheter och skript",
    "story": ("GUS har hittat ett skript som ska avkoda en signal från servern. Det är inte körbart. Nyckeln till serverrummet "
              "ligger dessutom i en fil som vem som helst får läsa. \"Det är precis så läckor börjar\", säger han. "
              "\"Rätta till det.\""),
    "learn": ("Varje fil har rättigheter för tre grupper: ägaren, gruppen och alla andra. Varje grupp kan få läsa (r), skriva (w) "
              "och köra (x). `ls -l` visar dem i början av raden:\n"
              "$ -rwxr-xr--   1 agent  staff  120 ...\n"
              "Läs det så: första tecknet är typ (- fil, d mapp). Sedan tre grupper om tre tecken: `rwx` för ägaren, "
              "`r-x` för gruppen, `r--` för alla andra.\n\n"
              "- `chmod +x fil` gör en fil körbar.\n"
              "- `chmod 600 fil` ger bara ägaren läs och skriv. Siffrorna är r=4, w=2, x=1 och summeras per grupp: "
              "6 är 4+2, alltså rw.\n"
              "- `./skript.sh` kör en fil i mappen du står i. Punkten och snedstrecket behövs.\n\n"
              "Ett skript är en textfil vars första rad, den så kallade shebang, talar om vilket program som ska köra den: "
              "`#!/bin/bash`."),
    "build": build6,
    "cheats": [("ls -l", "visa rättigheter, ägare och storlek"), ("chmod +x fil", "gör filen körbar"),
               ("chmod 600 fil", "bara ägaren får läsa och skriva"), ("chmod 755 fil", "ägaren allt, andra läsa och köra"),
               ("./skript.sh", "kör ett skript i nuvarande mapp"), ("#!/bin/bash", "första raden i ett skript")],
    "outro": "GUS: \"Nu är nyckeln låst och skriptet körbart. Att skriva egna skript är som att ge terminalen ett minne.\"",
    "missions": [
        {"text": "Titta på rättigheterna för filerna i `verktyg`. Vilken rättighetssträng har `avkoda.sh`? Svara med de tio tecknen, till exempel `-rwxr-xr-x`.",
         "hints": ["`ls -l` visar rättigheterna längst till vänster.", "Skriv `ls -l verktyg` och läs raden för avkoda.sh."],
         "sol": ["ls -l verktyg", ("svar", "-rw-r--r--")], "ans": "-rw-r--r--", "xp": 10,
         "after": "`rw-` för ägaren, `r--` för gruppen och `r--` för alla andra. Ingen x någonstans, så filen kan läsas men inte köras."},
        {"text": "Försök köra `avkoda.sh` med `./verktyg/avkoda.sh`. Det kommer misslyckas. Det är meningen.",
         "hints": ["Skriv sökvägen till filen med `./` framför.", "Skriv `./verktyg/avkoda.sh`."],
         "sol": ["./verktyg/avkoda.sh"], "check": lambda g: ranfail(g, r"avkoda\.sh"), "xp": 5,
         "after": "Permission denied. Terminalen vägrar för att filen saknar x. Det är inget fel på skriptet."},
        {"text": "Gör `verktyg/avkoda.sh` körbar.",
         "hints": ["`chmod` ändrar rättigheter. Plus x lägger till rätten att köra.", "Skriv `chmod +x verktyg/avkoda.sh`."],
         "sol": ["chmod +x verktyg/avkoda.sh"], "check": lambda g: mode(g, "verktyg/avkoda.sh") & 0o100, "xp": 10,
         "after": "Kontrollera med `ls -l verktyg`. Nu står det ett x på raden."},
        {"text": "Kör skriptet. Vilken kod skriver det ut? Svara med koden.",
         "hints": ["Samma kommando som förut, nu när det får köras.", "Skriv `./verktyg/avkoda.sh`."],
         "sol": ["./verktyg/avkoda.sh", ("svar", "MORGONFLY")], "ans": "MORGONFLY", "xp": 10,
         "after": "Du körde ett program du kan läsa själv. Öppna det med `cat verktyg/avkoda.sh` och se hur lite det är."},
        {"text": "Nyckelfilen `hemlig.nyckel` är läsbar för alla. Se till att bara du får läsa och skriva den, och att ingen annan får något.",
         "hints": ["Talet 600 ger ägaren rw och ingen annan något.", "Skriv `chmod 600 hemlig.nyckel`."],
         "sol": ["chmod 600 hemlig.nyckel"], "check": lambda g: (mode(g, "hemlig.nyckel") & 0o077) == 0 and (mode(g, "hemlig.nyckel") & 0o600) == 0o600, "xp": 15,
         "after": "Så gör man med privata nycklar. SSH vägrar faktiskt använda en nyckelfil som andra kan läsa."},
        {"text": "Skriv ett eget skript `hej.sh` som skriver ut en hälsning. Det ska ha shebang, vara körbart och du ska köra det.",
         "hints": ["Tre steg: skriv `#!/bin/bash` på första raden med `echo ... >`, lägg till en rad med `>>`, kör `chmod +x` och sedan `./hej.sh`.",
                   "Skriv:\n$ echo '#!/bin/bash' > hej.sh\n$ echo 'echo hej från terminalen' >> hej.sh\n$ chmod +x hej.sh\n$ ./hej.sh"],
         "sol": ["echo '#!/bin/bash' > hej.sh", "echo 'echo hej från terminalen' >> hej.sh", "chmod +x hej.sh", "./hej.sh"],
         "check": lambda g: isfile(g, "hej.sh") and read(g, "hej.sh").startswith("#!") and (mode(g, "hej.sh") & 0o100)
                            and any(e["ec"] == 0 and re.match(r"^(\./|~/|\S*/)?hej\.sh(\s|$)", e["cmd"].strip()) for e in g.mh),
         "xp": 25,
         "after": "Du har skrivit ett program. Allt som du kan göra i terminalen kan sparas i ett skript och köras med ett kommando."},
    ],
}

# ------------------------------------------------------------ nivå 7: miljö och processer


def build7(g):
    W(g, "verktyg/hej", '#!/bin/bash\necho "Hej från verktyg. Det här körde du utan sökväg tack vare PATH."\n', mode=0o755)
    W(g, "anteckningar.txt", "Något kör på servern och det borde det inte.\n")
    D(g, "projekt")
    spawn_spok(g)


L7 = {
    "title": "Miljö och processer",
    "story": ("Larmet på nod-7 visar hög belastning. GUS misstänker att ett program går i bakgrunden som inte borde göra det. "
              "\"Ett av dem heter spok\", säger han. \"Det låter inte som något vi har installerat.\" Innan du hittar det "
              "behöver du förstå hur terminalen minns saker."),
    "learn": ("Terminalen har ett minne som kallas miljön.\n"
              "- `export NAMN=värde` skapar en variabel. `echo $NAMN` skriver ut den.\n"
              "- `alias ll='ls -l'` skapar en genväg. Skriv `ll` sedan.\n"
              "- `PATH` är en lista med mappar där terminalen letar efter kommandon. Lägger du en mapp i `PATH` går programmen där "
              "att köra utan sökväg.\n\n"
              "Processer är program som körs just nu:\n"
              "- `ps aux` listar alla. Skicka det genom `grep namn` för att hitta en.\n"
              "- `kill PID` ber en process avsluta. PID är numret i andra kolumnen i `ps aux`.\n"
              "- `pgrep namn` skriver bara ut numret. Och `$(kommando)` byts ut mot vad kommandot skriver ut, "
              "så `kill $(pgrep spok)` hittar och avslutar på en gång.\n\n"
              "Den här nivån bryter mot en regel: vi rör riktiga processer. Döda bara den som spelet pekar ut."),
    "build": build7,
    "cheats": [("export NAMN=värde", "skapa en variabel"), ("echo $NAMN", "skriv ut en variabel"),
               ("alias ll='ls -l'", "skapa en genväg"), ("export PATH=$PATH:~/mapp", "lägg till mapp i kommandolistan"),
               ("ps aux | grep namn", "hitta en process"), ("pgrep namn", "skriv ut PID för en process"),
               ("kill PID", "be en process avsluta"), ("$(kommando)", "byt ut mot kommandots utskrift")],
    "outro": "GUS: \"Spok är borta. Du vet nu hur terminalen minns, och hur du stänger av något som inte ska köra.\"",
    "missions": [
        {"text": "Skriv ut vad variabeln `HOME` innehåller.",
         "hints": ["Variabler skrivs ut med `echo` och ett dollartecken framför namnet.", "Skriv `echo $HOME`."],
         "sol": ["echo $HOME"], "check": lambda g: ran(g, r"echo\s+.*\$\{?HOME"), "xp": 5,
         "after": "Dollartecknet betyder ersätt med värdet. `echo $USER`, `echo $PATH` och `echo $SHELL` visar andra."},
        {"text": "Skapa en egen variabel `KODNAMN` med valfritt värde.",
         "hints": ["Skriv `export`, sedan namn, likamed-tecken och värde. Inga mellanslag runt likamed.", "Skriv `export KODNAMN=uggla`."],
         "sol": ["export KODNAMN=uggla"], "check": lambda g: re.search(r'KODNAMN="?\w', state(g, "env")), "xp": 10,
         "after": "`export` gör variabeln tillgänglig för program du startar. Så konfigureras det mesta: API-nycklar, språk och färger."},
        {"text": "Skriv ut din nya variabel `KODNAMN`.",
         "hints": ["Samma sak som med `HOME`.", "Skriv `echo $KODNAMN`."],
         "sol": ["echo $KODNAMN"], "check": lambda g: ran(g, r"echo\s+.*\$\{?KODNAMN"), "xp": 5,
         "after": "Variabeln finns kvar mellan kommandona, men bara i det här fönstret. Ett nytt terminalfönster börjar från noll. Det löser vi i nästa nivå."},
        {"text": "Skapa en genväg `ll` som kör `ls -l`.",
         "hints": ["`alias`, sedan namn, likamed-tecken och kommandot inom citattecken.", "Skriv `alias ll='ls -l'`."],
         "sol": ["alias ll='ls -l'"], "check": lambda g: re.search(r"^alias ll=", state(g, "alias"), re.M), "xp": 10,
         "after": "Bara det som du skriver ofta är värt en genväg. Lång lista över ett långt kommando är ett bra tecken på ett alias."},
        {"text": "Använd din genväg: skriv `ll`.",
         "hints": ["Skriv bara namnet på aliaset.", "Skriv `ll`."],
         "sol": ["ll"], "check": lambda g: any(e["ec"] == 0 and re.match(r"^ll\b", e["cmd"].strip()) for e in g.mh), "xp": 5,
         "after": "Det där sparade fem tecken. Multiplicera med hundra gånger om dagen."},
        {"text": "Lägg mappen `verktyg` i din `PATH`, så att du kan köra programmet `hej` i den utan att skriva sökväg. Kör sedan `hej`.",
         "hints": ["`export PATH=$PATH:...` lägger till en mapp sist i listan. `~/verktyg` är mappen.", "Skriv `export PATH=$PATH:~/verktyg` och sedan `hej`."],
         "sol": ["export PATH=$PATH:~/verktyg", "hej"],
         "check": lambda g: g.root + "/verktyg" in state(g, "env") and any(e["ec"] == 0 and e["cmd"].strip() == "hej" for e in g.mh), "xp": 20,
         "after": "Så fungerar det när du installerar ett program: ett verktyg ligger i en mapp som finns i PATH. Nu vet du varför."},
        {"text": "Något som heter `spok` kör i bakgrunden. Hitta det, och svara med dess PID. PID är numret i andra kolumnen.",
         "hints": ["`ps aux` listar alla processer. Skicka genom `grep spok` för att bara se din.", "Skriv `ps aux | grep spok`. Ta numret på raden där spok körs, inte raden för grep."],
         "sol": ["ps aux | grep spok", ("svar", lambda g: g.S["pid"])], "ans": lambda g: str(g.S["pid"]), "xp": 15,
         "after": "Du kommer alltid se en extra rad för `grep` själv i sådana sökningar. Att veta det är halva vinsten."},
        {"text": "Avsluta processen `spok`.",
         "hints": ["`kill` följt av PID. Eller `pgrep spok` som ger dig numret.", "Skriv `kill PID` med numret du hittade."],
         "sol": ["kill $(pgrep spok)"], "check": lambda g: bool(g.procs) and g.procs[0].poll() is not None, "xp": 20,
         "after": "`kill` ber processen avsluta. Hänger den kvar finns `kill -9 PID`, men försök alltid vänligt först."},
    ],
}

# ------------------------------------------------------------ nivå 8: personlig


def build8(g):
    D(g, "projekt")
    D(g, "verktyg")
    W(g, "exempel_zshrc.txt", """# Så här kan en riktig ~/.zshrc se ut. Allt här körs varje gång du öppnar ett terminalfönster.

# Navigering
alias ..='cd ..'
alias ...='cd ../..'
alias ll='ls -lah'
alias projekt='cd ~/Documents/projekt'

# Säkrare
alias rm='rm -i'
alias cp='cp -i'

# Sådant man annars googlar varje gång
alias minip='curl -s ifconfig.me'
alias vader='curl -s "wttr.in/Stockholm?format=3"'
alias portar='lsof -i -P | grep LISTEN'
alias storlek='du -sh * | sort -h'
alias serva='python3 -m http.server 8000'
alias ren='find . -name ".DS_Store" -delete'
alias hitta='grep -rn'

# Git
alias gs='git status -sb'
alias gl='git log --oneline --graph -15'

# Funktioner: som alias, men med argument och flera steg
mkcd() { mkdir -p "$1" && cd "$1"; }
backup() { cp "$1" "$1.bak-$(date +%F)"; }
uppdatera() { brew update && brew upgrade; }

# Miljö
export EDITOR=nano
export HISTSIZE=10000
export PATH="$HOME/bin:$PATH"

# Prompt: mapp i cyan, sedan ett dollartecken
export PS1='\\[\\e[36m\\]\\w\\[\\e[0m\\] \\$ '
""")


def _rc(g):
    return read(g, ".mittrc")


L8 = {
    "title": "Gör den till din",
    "story": ("GUS tittar på dig över kanten av sin kaffekopp. \"Du skriver samma saker om och om igen. Det gör alla. "
              "Skillnaden är att de som kan terminalen bygger om den tills den skriver åt dem.\" "
              "Här ska du få din egen terminal: egna genvägar, egen prompt och egna små funktioner."),
    "learn": ("Terminalen läser en fil varje gång den startar. På din Mac heter den `~/.zshrc`. Allt du skriver i den gäller "
              "i varje nytt fönster. Här i spelet har du din egen, `.mittrc`, och du laddar den med `source .mittrc`.\n\n"
              "Vad man kan lägga i den:\n"
              "- alias för allt du skriver ofta: `alias gs='git status'`\n"
              "- funktioner, som är alias med argument: `mkcd() { mkdir -p \"$1\" && cd \"$1\"; }`\n"
              "- variabler: `export EDITOR=nano`\n"
              "- prompten, alltså texten före markören, i variabeln `PS1`. `\\w` är mappen, `\\u` ditt namn och `\\e[35m` "
              "gör resten magenta. Slå på prompten i spelet så syns det direkt nedan.\n\n"
              "Filen `exempel_zshrc.txt` i din hemmapp är en riktig konfig som visar hur långt det går: väder, "
              "din IP-adress, en lokal webbserver, git-genvägar, säkrare `rm`, backup med datum. "
              "Läs den när du är klar med det första. Du kan ta med det du gillar."),
    "build": build8,
    "cheats": [("alias namn='kommando'", "skapa en genväg"), ("unalias -a", "ta bort alla genvägar just nu"),
               ("source .mittrc", "ladda om en konfigfil"), ("PS1='...'", "ändra prompten"),
               ("namn() { ...; }", "skapa en funktion"), ("echo '...' >> fil", "bygg en konfigfil rad för rad"),
               ("~/.zshrc", "din riktiga konfigfil på Mac")],
    "outro": ("GUS: \"Nu ser din terminal ut som din. Filen `.mittrc` ligger i din hemmapp. På din riktiga Mac är motsvarigheten "
              "`~/.zshrc`. Klistra in det du vill ha, kör `source ~/.zshrc`, och du har samma genvägar överallt. "
              "Jag har sparat en färdig kopia åt dig i `~/.terminalspelet/min_zshrc.txt`.\""),
    "on_done": lambda g: shutil.copy(g.P(".mittrc"), os.path.join(os.path.dirname(g.root), "min_zshrc.txt")) if isfile(g, ".mittrc") else None,
    "missions": [
        {"text": "Skapa en genväg `hem` som tar dig till din hemmapp.",
         "hints": ["`alias`, sedan namn, likamed-tecken och kommandot inom citattecken. Kommandot är det du lärde dig i nivå 1.", "Skriv `alias hem='cd ~'`."],
         "sol": ["alias hem='cd ~'"], "check": lambda g: re.search(r"^alias hem='cd", state(g, "alias"), re.M), "xp": 10,
         "after": "Genvägen finns nu i det här fönstret. Ett nytt fönster har den inte, tills vi sparar den."},
        {"text": "Gå först in i mappen `projekt`. Använd sedan din nya genväg för att komma hem.",
         "hints": ["Ta `cd projekt`, sedan skriver du bara namnet på genvägen.", "Skriv `cd projekt` och sedan `hem`."],
         "sol": ["cd projekt", "hem"],
         "check": lambda g: lastcmd(g) == "hem" and g.last["ec"] == 0 and g.last["before"] != g.root and g.cwd == g.root, "xp": 5,
         "after": "Du kan skriva egna versioner av vad som helst. Vissa lägger genvägar för varje projektmapp de jobbar i."},
        {"text": "Spara minst två alias i filen `.mittrc` i din hemmapp, till exempel `ll` och `hem`. Bygg filen rad för rad med `echo` och `>>`.",
         "hints": ["Du har `>>` sen nivå 3. Varje rad ska vara ett alias, och citera det med enkla citattecken.",
                   "Skriv:\n$ echo \"alias ll='ls -lah'\" >> .mittrc\n$ echo \"alias hem='cd ~'\" >> .mittrc"],
         "sol": ["echo \"alias ll='ls -lah'\" >> .mittrc", "echo \"alias hem='cd ~'\" >> .mittrc"],
         "check": lambda g: len(re.findall(r"^alias \S+=", _rc(g), re.M)) >= 2, "xp": 15,
         "after": "Så gör riktiga konfigfiler också: rader med kommandon som körs varje gång du startar. Du skapade just en."},
        {"text": "Simulera att du startar om terminalen. Ta först bort alla alias med `unalias -a`, och ladda sedan om dem från filen med `source .mittrc`.",
         "hints": ["Två kommandon i ordning. Det första rensar, det andra läser filen.", "Skriv `unalias -a` och sedan `source .mittrc`."],
         "sol": ["unalias -a", "source .mittrc"],
         "check": lambda g: (lambda u, s: u is not None and s is not None and s > u
                             and re.search(r"^alias ll=", state(g, "alias"), re.M) and re.search(r"^alias hem=", state(g, "alias"), re.M))(
             next((i for i, e in enumerate(g.mh) if e["ec"] == 0 and re.search(r"\bunalias\b", e["cmd"])), None),
             next((i for i, e in enumerate(g.mh) if e["ec"] == 0 and re.match(r"^(source|\.)\s+\S*\.mittrc", e["cmd"].strip())), None)),
         "xp": 15,
         "after": "`source` kör en fil i det pågående skalet. På din Mac gör terminalen exakt det med `~/.zshrc` när ett fönster öppnas."},
        {"text": "Byt din prompt. Sätt `PS1` till något som innehåller mappen (`\\w`) och en färg. Spelets prompt ändras direkt.",
         "hints": ["`\\w` är aktuell mapp. `\\[\\e[35m\\]` startar magenta och `\\[\\e[0m\\]` slutar. Sätt hela värdet inom enkla citattecken.",
                   "Skriv `PS1='\\[\\e[35m\\]\\w ▸ \\[\\e[0m\\]'`. Prova sedan att ändra färgtalet: 31 röd, 32 grön, 33 gul, 34 blå, 36 cyan."],
         "sol": ["PS1='\\[\\e[35m\\]\\w ▸ \\[\\e[0m\\]'"],
         "check": lambda g: re.search(r"\\[wW]", state(g, "ps1")) and re.search(r"\\(e|033)\[", state(g, "ps1")), "xp": 20,
         "after": "Prompten är vad du tittar på hela dagen. Vissa lägger in git-gren, klockslag eller fjolårets tid till nästa middag. Verktyget Starship gör det med ett par rader."},
        {"text": "Skriv en funktion `mkcd` som skapar en mapp och går in i den. Testa den med `mkcd labb/test`.",
         "hints": ["Funktion: `namn() { kommando1 && kommando2; }`. `$1` är det första argumentet du skriver efter namnet.",
                   "Skriv `mkcd() { mkdir -p \"$1\" && cd \"$1\"; }` och sedan `mkcd labb/test`."],
         "sol": ["mkcd() { mkdir -p \"$1\" && cd \"$1\"; }", "mkcd labb/test"],
         "check": lambda g: "mkcd" in state(g, "funcs") and any(e["ec"] == 0 and re.match(r"^mkcd\s+\S+", e["cmd"].strip()) for e in g.mh)
                            and g.cwd != g.root and os.path.isdir(g.cwd), "xp": 25,
         "after": "En funktion är ett alias som kan ta emot argument och köra flera steg. Nästan alla har en `mkcd` någonstans i sin konfig."},
        {"text": "Läs `exempel_zshrc.txt`. Vilket alias där startar en lokal webbserver? Svara med aliasets namn.",
         "hints": ["Öppna filen med det du lärde dig i nivå 2.", "Skriv `cat exempel_zshrc.txt`. Leta efter `python3 -m http.server`."],
         "sol": ["cat exempel_zshrc.txt", ("svar", "serva")], "ans": "serva", "xp": 10,
         "after": "Det är en bråkdel av vad som går. Du kan lägga vädret i prompten, ha ett kommando som rensar Downloads eller ett som skapar en ny projektmapp med rätt filer. Allt börjar med ett alias."},
        {"text": "Gå hem med `cd ~`. Gör sedan klart din konfig: lägg till en `PS1`-rad och minst en `export`-rad i `.mittrc`, så att filen har både alias, prompt och variabel.",
         "hints": ["Använd `echo` och `>>` som förut. Lägg raden inom enkla citattecken så att backslash följer med.",
                   "Skriv:\n$ echo 'PS1=\"\\[\\e[35m\\]\\w ▸ \\[\\e[0m\\] \"' >> .mittrc\n$ echo 'export EDITOR=nano' >> .mittrc"],
         "sol": ["cd ~", "echo 'PS1=\"\\[\\e[35m\\]\\w ▸ \\[\\e[0m\\] \"' >> .mittrc", "echo 'export EDITOR=nano' >> .mittrc"],
         "check": lambda g: re.search(r"^(export )?PS1=", _rc(g), re.M) and re.search(r"^export \w+=", _rc(g), re.M)
                            and len(re.findall(r"^alias \S+=", _rc(g), re.M)) >= 2, "xp": 20,
         "after": "Klart. Kopian av din fil sparas när nivån är slut, så att du kan klistra in den i `~/.zshrc` på riktigt."},
    ],
}

# ------------------------------------------------------------ nivå 9: verktygslådan


def build9(g):
    r = random.Random(9 * 1000003 + g.seed)
    for n in ("a_utkast", "b_bilaga", "c_notering", "d_moten", "e_agenda"):
        W(g, "dokument/%s.txt" % n, prose(r, 4))
    W(g, "plan.txt", "Lansering av Norrsken i oktober.\nBudget för Norrsken är låst.\nEndast styrelsen känner till Norrsken.\nAgenda följer.\n")
    posts = [("Annonsering", "marknad", 45000), ("Webb", "marknad", 22000), ("Licenser", "it", 18000),
             ("Konsult", "it", 60000), ("Resor", "drift", 9500), ("Utbildning", "drift", 12500),
             ("Event", "marknad", 31000), ("Hosting", "it", 14000)]
    W(g, "budget.csv", "post,kategori,belopp\n" + "\n".join("%s,%s,%d" % p for p in posts) + "\n")
    g.S["summa"] = str(sum(p[2] for p in posts))
    for i in range(12):
        W(g, "tmp/%s/fil%d.tmp" % (r.choice(["a", "b", "c"]), i), "skräp\n")
    W(g, "tmp/a/behall.keep", "spara mig\n")
    W(g, "tmp/b/behall2.keep", "spara mig också\n")


def _keeps(g):
    return len([1 for p in walk_files(g) if p.endswith(".keep")])


L9 = {
    "title": "Verktygslådan",
    "story": ("Läckan är nästan hittad, men först behöver du städa upp efter dig och tvätta en plan så att den kan delas. "
              "\"Nu ska du få se vad terminalen kan när man slutar göra en sak i taget\", säger GUS. "
              "\"Slingor, textbyten, summor och packade filer. Och nej, det är inte svårare än det du redan kan.\""),
    "learn": ("De här verktygen är det som får proffs att se ut som magiker.\n"
              "- `for f in *.txt; do kommando \"$f\"; done` kör ett kommando på varje fil som matchar.\n"
              "- `sed 's/gammalt/nytt/g' fil` byter text. Utskriften går till skärmen, så lägg till `> nyfil`.\n"
              "- `awk -F, '{s+=$3} END {print s}' fil` summerar kolumn 3 i en csv-fil. `NR>1` hoppar över rubrikraden.\n"
              "- `find . -name \"*.tmp\" -delete` hittar och raderar i samma steg.\n"
              "- `a && b` kör b bara om a lyckades. `a || b` kör b bara om a misslyckades.\n"
              "- `$(kommando)` byts ut mot kommandots utskrift. `$(date +%F)` blir dagens datum.\n"
              "- `tar -czf arkiv.tar.gz mapp` packar en mapp till en fil. `tar -xzf arkiv.tar.gz` packar upp."),
    "build": build9,
    "cheats": [("for f in *.txt; do ...; done", "kör något på varje fil"), ("sed 's/a/b/g' fil", "byt text"),
               ("awk -F, '{s+=$3} END {print s}' fil", "summera en kolumn"), ("find . -name \"*.tmp\" -delete", "hitta och radera"),
               ("a && b", "kör b bara om a gick bra"), ("$(date +%F)", "dagens datum, 2026-09-29"),
               ("tar -czf x.tar.gz mapp", "packa en mapp"), ("tar -xzf x.tar.gz", "packa upp")],
    "outro": "GUS: \"Slingor, textbyten, summor och arkiv. Du har nu mer verktyg än de flesta som säger att de kan terminalen.\"",
    "missions": [
        {"text": "Alla filer i `dokument` slutar på `.txt`. Byt ändelsen till `.md` på alla på en gång med en `for`-slinga.",
         "hints": ["Slingan går igenom filerna. `${f%.txt}` tar bort `.txt` från namnet i `f`.",
                   "Skriv `for f in dokument/*.txt; do mv \"$f\" \"${f%.txt}.md\"; done`."],
         "sol": ["for f in dokument/*.txt; do mv \"$f\" \"${f%.txt}.md\"; done"],
         "check": lambda g: len([f for f in os.listdir(g.P("dokument")) if f.endswith(".md")]) == 5 and not [f for f in os.listdir(g.P("dokument")) if f.endswith(".txt")],
         "xp": 25, "after": "Tänk dig 500 filer i stället för 5. Det tar lika lång tid att skriva."},
        {"text": "`plan.txt` nämner `Norrsken` och ska delas. Skapa `plan_ren.txt` där ordet har bytts mot `PROJEKT-X`. Originalet ska vara orört.",
         "hints": ["`sed 's/gammalt/nytt/g'` byter alla förekomster. Skicka resultatet till en ny fil.", "Skriv `sed 's/Norrsken/PROJEKT-X/g' plan.txt > plan_ren.txt`."],
         "sol": ["sed 's/Norrsken/PROJEKT-X/g' plan.txt > plan_ren.txt"],
         "check": lambda g: isfile(g, "plan_ren.txt") and "Norrsken" not in read(g, "plan_ren.txt") and "PROJEKT-X" in read(g, "plan_ren.txt") and "Norrsken" in read(g, "plan.txt"),
         "xp": 20, "after": "`sed` är ett sök-och-ersätt som fungerar på filer av vilken storlek som helst."},
        {"text": "Vad blir summan av kolumnen `belopp` i `budget.csv`? Hoppa över rubrikraden. Svara med talet.",
         "hints": ["`awk` kan räkna. `-F,` säger att kolumnerna skiljs med komma, `NR>1` hoppar över första raden.",
                   "Skriv `awk -F, 'NR>1 {s+=$3} END {print s}' budget.csv`."],
         "sol": ["awk -F, 'NR>1 {s+=$3} END {print s}' budget.csv", ("svar", lambda g: g.S["summa"])], "ans": lambda g: g.S["summa"], "xp": 25,
         "after": "`awk` är ett helt litet programmeringsspråk. Det du gjorde nu var en enda rad ur en svensk Excel-formel."},
        {"text": "Ta bort alla `.tmp`-filer i `tmp` och alla dess undermappar, med ett enda kommando. Filerna som slutar på `.keep` ska vara kvar.",
         "hints": ["`find` med `-name` hittar dem. Lägg till en åtgärd på slutet som tar bort dem.", "Skriv `find tmp -name \"*.tmp\" -delete`."],
         "sol": ["find tmp -name \"*.tmp\" -delete"],
         "check": lambda g: not [p for p in walk_files(g) if p.endswith(".tmp")] and _keeps(g) == 2, "xp": 20,
         "after": "Kör alltid `find ... ` utan `-delete` först för att se vad som kommer försvinna. Byt sedan ut."},
        {"text": "Skapa mappen `arbete` och gå in i den, i ett enda kommandorad. Andra kommandot ska bara köras om det första lyckades.",
         "hints": ["`&&` kopplar ihop två kommandon så att det andra bara körs om det första lyckas.", "Skriv `mkdir arbete && cd arbete`."],
         "sol": ["mkdir arbete && cd arbete"], "check": lambda g: g.cwd == g.P("arbete"), "xp": 10,
         "after": "`&&` gör att du slipper fortsätta i fel mapp när något gick fel. Det är säkerhetsbältet i skript."},
        {"text": "Gå hem. Skapa en mapp som heter `backup_` följt av dagens datum, med hjälp av `$(date +%F)`.",
         "hints": ["`date +%F` skriver ut datumet som 2026-09-29. `$(...)` byter ut sig själv mot det.", "Skriv `mkdir backup_$(date +%F)`, efter `cd ~`."],
         "sol": ["cd ~", "mkdir backup_$(date +%F)"],
         "check": lambda g: any(os.path.basename(d) == "backup_" + time.strftime("%Y-%m-%d") for d in walk_dirs(g)), "xp": 15,
         "after": "Det är så dagliga backuper får unika namn utan att någon hittar på ett. Datumet i filnamn är också en bra vana."},
        {"text": "Packa mappen `dokument` till en komprimerad fil `backup.tar.gz`. Du ska stå i din hemmapp.",
         "hints": ["`tar -czf` skapar en komprimerad arkivfil. Först namnet på arkivet, sedan det som ska packas.", "Skriv `tar -czf backup.tar.gz dokument`."],
         "sol": ["cd ~", "tar -czf backup.tar.gz dokument"],
         "check": lambda g: isfile(g, "backup.tar.gz") and any(n.startswith("dokument") for n in tarfile.open(g.P("backup.tar.gz")).getnames()), "xp": 20,
         "after": "Flaggorna är c för create, z för gzip och f för fil. Uppackning är `tar -xzf`. Nu behöver du aldrig googla det igen."},
    ],
}

# ------------------------------------------------------------ nivå 10: finalen


def build10(g):
    r = random.Random(10 * 1000003 + g.seed)
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
    W(g, "loggar/auth.log", "\n".join("2026-09-28 %s %s" % (hms(t), m) for t, m in auth) + "\n")
    files = ["kalender.xlsx", "prislista.pdf", "organisation.pptx", "avtal_mall.docx", "styrelsepromemoria.pdf"]
    fa = []
    for _ in range(160):
        fa.append((r.randint(6 * 3600, 23 * 3600 + 3000), "%s %s %s" % (r.choice(users), r.choice(["READ", "COPY"]), r.choice(files))))
    fa.append((9 * 3600 + 730, "lfalk READ kalender.xlsx"))
    fa.append((85743, "lfalk COPY norrsken_plan.pdf -> /media/usb0"))
    fa.append((85900, "lfalk SEND norrsken_plan.pdf -> extern"))
    fa.sort()
    W(g, "loggar/filaccess.log", "\n".join("2026-09-28 %s %s" % (hms(t), m) for t, m in fa) + "\n")
    for u in ["lfalk", "tnilsson", "mbergman"]:
        D(g, "hemmappar/%s/.cache" % u)
        W(g, "hemmappar/%s/dokument/anteckning.txt" % u, prose(r, 3))
    W(g, "hemmappar/lfalk/.utkorg/notering.txt", "Skickat via privat mejl till erik@konkurrent-x.example.\nRadera den här mappen på fredag.\n")
    W(g, "hemmappar/lfalk/dokument/lunch.txt", "Fredag: sushi.\n")
    spawn_spok(g)


L10 = {
    "title": "Läckan",
    "story": ("Det är fredag kväll. Du har provat allt: vandrat i mappar, läst loggar, sökt, rört, låst och skriptat. "
              "GUS öppnar tre filer åt dig: `auth.log`, `filaccess.log` och en mapp med alla anställdas hemmappar. "
              "\"Nu har du alla verktyg\", säger han. \"Någon loggade in efter arbetstid, kopierade Norrsken-planen och skickade "
              "den vidare. Ta reda på vem, vad och vart. Och stäng ner det som fortfarande kör.\""),
    "learn": ("Inga nya kommandon här. Allt du behöver har du redan lärt dig. Använd `hint` om du kör fast, "
              "men prova först. Tänk på: `grep`, `find`, `cat`, `ls -a`, `>`, `chmod` och `kill`."),
    "build": build10,
    "cheats": [("grep 23:47 loggar/auth.log", "sök tidsstämpel i en logg"), ("find . -name \".*\" -type d", "hitta dolda mappar")],
    "outro": "GUS: \"Rapporten är skriven, låst och processen är stoppad. Det är mer än många avdelningar får ihop på en vecka.\"",
    "missions": [
        {"text": "Den misstänkta inloggningen skedde klockan 23:47. Vem loggade in? Sök i `loggar/auth.log` och svara med användarnamnet.",
         "hints": ["`grep` med tiden som sökord.", "Skriv `grep 23:47 loggar/auth.log`."],
         "sol": ["grep 23:47 loggar/auth.log", ("svar", "lfalk")], "ans": "lfalk", "xp": 20,
         "after": "En enda rad bland tvåhundra. Du upptäckte det på under en sekund."},
        {"text": "Vilken fil kopierade den användaren? Sök i `loggar/filaccess.log` och svara med filnamnet.",
         "hints": ["Sök på användarnamnet du hittade.", "Skriv `grep lfalk loggar/filaccess.log`."],
         "sol": ["grep lfalk loggar/filaccess.log", ("svar", "norrsken_plan.pdf")], "ans": "norrsken_plan.pdf", "xp": 20,
         "after": "Tre rader, och en av dem är just den fil som läckt. Allt sitter ihop."},
        {"text": "Användaren hade en dold mapp i sin hemmapp, under `hemmappar`. Hitta den, läs anteckningen och svara med domänen filen skickades till, till exempel `foretag.example`.",
         "hints": ["Dolda mappar börjar med punkt. `find` med `-name` och `-type d` hittar dem.", "Skriv `find hemmappar -name \".*\" -type d`. Det finns en som inte ser ut som en cache. Läs filen i den med `cat`."],
         "sol": ["find hemmappar -name \".*\" -type d", "cat hemmappar/lfalk/.utkorg/notering.txt", ("svar", "konkurrent-x.example")],
         "ans": ["konkurrent-x.example", "erik@konkurrent-x.example"], "xp": 25,
         "after": "Du hittade det som var gömt med `find`. Dolt i ett filsystem är aldrig osynligt för den som vet hur man ber om det."},
        {"text": "Skriv rapporten. Skapa `rapport.txt` i din hemmapp som nämner personens användarnamn, filens namn och domänen. Gör den läsbar bara för dig.",
         "hints": ["`echo` och `>` skapar filen. `chmod 600` låser den.", "Skriv `echo \"lfalk kopierade norrsken_plan.pdf och skickade den till konkurrent-x.example\" > ~/rapport.txt` och sedan `chmod 600 ~/rapport.txt`."],
         "sol": ["echo \"lfalk kopierade norrsken_plan.pdf och skickade den till konkurrent-x.example\" > ~/rapport.txt", "chmod 600 ~/rapport.txt"],
         "check": lambda g: isfile(g, "rapport.txt") and all(x in read(g, "rapport.txt").casefold() for x in ("lfalk", "norrsken_plan.pdf", "konkurrent-x.example"))
                            and (mode(g, "rapport.txt") & 0o077) == 0, "xp": 30,
         "after": "Bevis och rättigheter i samma uppdrag. En rapport som alla kan läsa är i praktiken en ny läcka."},
        {"text": "Processen `spok` kör fortfarande och skickar ut data. Hitta den och stäng ner den.",
         "hints": ["Du har gjort det här. `pgrep` ger PID, `kill` stänger.", "Skriv `kill $(pgrep spok)`."],
         "sol": ["kill $(pgrep spok)"], "check": lambda g: bool(g.procs) and g.procs[0].poll() is not None, "xp": 20,
         "after": "Läckan är stoppad. Allt du behövde fanns i terminalen."},
    ],
}

EPILOGUE = (
    "GUS: \"Lena Falk hade kopierat planen till ett USB-minne och skickat den till en konkurrent. Din rapport ligger hos "
    "chefen. Du gick in i morse med en prompt och en kaffekopp. Nu kan du navigera, läsa, bygga, söka, koppla ihop "
    "kommandon, låsa filer, styra processer och skriva egna skript. Din terminal är dessutom din egen.\"\n\n"
    "GUS lägger till: \"Det räcker för att klara det mesta som du kommer råka ut för. Fortsätt skriva. "
    "Terminalen blir bara bättre av att användas.\""
)

LEVELS = [L1, L2, L3, L4, L5, L6, L7, L8, L9, L10]

# Kapitel 2 ligger i fall.py. Importen står sist eftersom fall.py hämtar hjälpfunktioner härifrån.
import fall  # noqa: E402

LEVELS = LEVELS + fall.CASES
EPILOGUE = fall.EPILOGUE
