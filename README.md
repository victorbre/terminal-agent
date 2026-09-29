# Terminalspelet (The Terminal Game)

Ett spel som lär dig terminalen genom att du kör riktiga kommandon på riktiga filer.
Spelet har två delar. Första delen är tio nivåer där du lär dig kommandona, med en gåta som löper genom dem: Projekt Norrsken har läckt. Andra delen, kapitel 2, är själva spelet: fem långa fall där en kris slår mot Fyrtornet AB och du gräver dig ner i loggar, skript och backuper för att ta reda på vad som hänt och vem som gjort det.

## Starta

```
cd ~/proj/terminal-agent
./spela
```

Kräver Python 3 (finns på din Mac). Första gången väljer du svenska eller engelska. Byt senare med
spelkommandot `språk` (nivån byggs då om), eller starta med `./spela --lang en` / `./spela --lang sv`.
Starta om från början med `./spela --nollstall`. Slutar du mitt i en nivå eller ett fall fortsätter du på samma uppdrag nästa gång.
Världarna slumpas för varje ny omgång, så loggar och siffror blir inte desamma om du spelar igen.

English: run `./spela --lang en`. The whole game, including file names in the levels, is available in English.

## Nivåerna

1. Kartan: `pwd`, `ls`, `cd`, Tab
2. Läs som en detektiv: `cat`, `head`, `tail`, `less`, `wc`, `file`
3. Bygg, flytta, städa: `mkdir`, `touch`, `cp`, `mv`, `rm`, `>`, `>>`, `*`
4. Spårhunden: `find`, `grep`
5. Rör och pipes: `|`, `sort`, `uniq`, `cut`
6. Rättigheter och skript: `chmod`, `./skript.sh`
7. Miljö och processer: `export`, `alias`, `PATH`, `ps`, `kill`
8. Gör den till din: egen konfigfil, alias, prompt, funktioner
9. Verktygslådan: `for`, `sed`, `awk`, `&&`, `$(...)`, `tar`
10. Läckan: allt tillsammans

## Kapitel 2: Mörkläggningen

Fyra dagar före lanseringen av Norrsken försvinner förbeställningarna. Här får du inga lektioner. Uppdragen frågar efter
vad du ska ta reda på, inte vilket kommando du ska köra. `hint` finns kvar, med tre steg från riktning till nästan färdig lösning.

11. Nattlarmet: loggar, cron och backuper. Vad gick sönder, när, och vad kan räddas?
12. Bomben: ett skript med gömd kod. `diff`, `base64 -d`, crontab och ändringshistorik.
13. Kontot: vems hand låg bakom ett konto? Inloggningslogg, DHCP och inventarielista.
14. Spåren efter: kommandohistorik, låsta nycklar och en anteckning som raderats men finns kvar i en backup.
15. Klockan tickar: städa upp, återställa 1 847 kunder ur en logg och skriva rapporten.

Rangerna efter Terminalmästare (Utredare, Kriminaltekniker, Kommissarie) delas ut under kapitel 2.

## Spelkommandon

`hint`, `mål`, `svar X`, `lär`, `fusklapp`, `poäng`, `lösning`, `hoppa`, `språk`, `:reset`, `sluta`.
De engelska namnen fungerar också: `goal`, `answer X`, `learn`, `cheatsheet`, `score`, `solution`, `skip`, `lang`, `quit`.
Allt annat du skriver körs som ett riktigt kommando.

## Säkerhet

Allt sker i `~/.terminalspelet/hem`. Spelet stoppar sökvägar utanför mappen och farliga
kommandon som `sudo`. Det är en spärr mot olyckor, inte ett säkerhetslås.
Nivå 7 och 10 startar en riktig bakgrundsprocess (`spok`), och fall 1 startar `natt_rensare`. Döda bara den som uppdraget pekar ut.

## Filer som spelet skapar

- `~/.terminalspelet/save.json`: din rang och hur långt du kommit
- `~/.terminalspelet/fusklapp.txt` (engelska: `cheatsheet.txt`): kommandona du lärt dig
- `~/.terminalspelet/min_zshrc.txt`: din egen konfig från nivå 8, redo att klistras in i `~/.zshrc`

Fallen (kapitel 2) skapar stora loggar, arkiv och bevisfiler i `hem`. Allt byggs om varje gång du börjar ett fall.

## Testa spelet

`python3 terminalspelet.py --selftest` (och `--selftest --lang en`) spelar igenom alla uppdrag automatiskt med de inbyggda
lösningarna och rapporterar vilka som inte går att klara.
