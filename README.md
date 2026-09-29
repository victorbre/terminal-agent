# Terminalspelet (The Terminal Game)

Ett spel som lär dig terminalen genom att du kör riktiga kommandon på riktiga filer.
En gåta löper genom tio nivåer: Projekt Norrsken har läckt, och du ska ta reda på hur.

## Starta

```
cd ~/proj/terminal-game
./spela
```

Kräver Python 3 (finns på din Mac). Första gången väljer du svenska eller engelska. Byt senare med
spelkommandot `språk` (nivån byggs då om), eller starta med `./spela --lang en` / `./spela --lang sv`.
Starta om från början med `./spela --nollstall`.

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

## Spelkommandon

`hint`, `mål`, `svar X`, `lär`, `fusklapp`, `poäng`, `lösning`, `hoppa`, `språk`, `:reset`, `sluta`.
De engelska namnen fungerar också: `goal`, `answer X`, `learn`, `cheatsheet`, `score`, `solution`, `skip`, `lang`, `quit`.
Allt annat du skriver körs som ett riktigt kommando.

## Säkerhet

Allt sker i `~/.terminalspelet/hem`. Spelet stoppar sökvägar utanför mappen och farliga
kommandon som `sudo`. Det är en spärr mot olyckor, inte ett säkerhetslås.
Nivå 7 och 10 startar en riktig bakgrundsprocess (`spok`) som du ska döda. Döda bara den.

## Filer som spelet skapar

- `~/.terminalspelet/save.json`: din rang och hur långt du kommit
- `~/.terminalspelet/fusklapp.txt` (engelska: `cheatsheet.txt`): kommandona du lärt dig
- `~/.terminalspelet/min_zshrc.txt`: din egen konfig från nivå 8, redo att klistras in i `~/.zshrc`

## Testa spelet

`python3 terminalspelet.py --selftest` (och `--selftest --lang en`) spelar igenom alla uppdrag automatiskt med de inbyggda
lösningarna och rapporterar vilka som inte går att klara.
