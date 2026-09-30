# SPARK Motion Pack · Arbeitsweise

Alles prozedural: Python (numpy/scipy/pillow) + ffmpeg, keine KI-Dienste. Was wo liegt und wie man es startet: `README.md`.
Designsystem (Codes, Taste, Rezepte, was verworfen ist): Skill `spark-motion`. Galerie des Systems: `styles/index.html`.

## Session

1. Diese Datei lesen, dann die `CLAUDE.md` des Projekts, an dem gearbeitet wird (z. B. `kickoff_loop/CLAUDE.md`).
2. Vadim steuert per Code (P17, S7 …) und Versionsnummer (v003). Vorschau zuerst, dann rendern. Nie raten, was er meint: nachsehen.
3. Am Ende: `CLAUDE.md` des Projekts nachziehen (Entscheidungen mit Befund, Offen-Liste), committen.

## Ein Projekt = ein Ordner + ein Skript

```
<projekt>/            CLAUDE.md (Vision, Stand, Entscheidungen, Offen), <projekt>.toml bzw. loop.toml (alle Stellschrauben),
                      ref/ (Referenzen), previz/vNNN/ (versionierte Vorschauen + report.txt + Kopie der Config),
                      weitere Ausgaben nach Zweck (print/, resolve/, photos/ …)
src/<projekt>.py      Einstieg + Logik, PEP-723-Kopf mit Abhaengigkeiten → `uv run src/<projekt>.py <befehl>`
src/<projekt>_*.py    weitere Teile nach Aufgabe (_video, _audio …), wenn eine Datei zu gross wird
```

Vorbild: `kickoff_loop/` + `src/kickoff_loop.py`. Ältere Ordner (`kickoff/`, `makernight/`, `styles/` …) sind eine Ausgabe
pro Skript ohne eigene CLAUDE.md; beim nächsten Anfassen auf dieses Schema bringen.

## Code

- **Keine Gestaltungswerte im Code.** Alles, was man drehen will, steht kommentiert in der TOML des Projekts, Einheit im Namen
  (`_s`, `_deg`, `_frac`, `_px`, `_cells`). Systemkonstanten (Paletten, Dither, Raster) leben in `src/styles.py`.
  Technische Konstanten im Code bekommen einen Namen und einen Kommentar, woher die Zahl kommt.
- `load()` prüft die Config am Anfang und sagt in Klartext, was falsch ist (statt nach Minuten Rendern abzubrechen).
- Docstrings sagen was und **warum**. Deutsch, im Code ASCII (ue/oe/ae) wie im Bestand.
- Bestehendes System wiederverwenden statt kopieren: `kickoff.py`/`styles.py` haben Hooks (`layout`, `type_fn`, `spark_fn`).
- Renders nach Inhalt cachen (Hash aus Stil + Quelltext), Pools nur hinter `if __name__ == "__main__"` (macOS spawnt).

## Prüfen statt Anschauen

Jede Vorschau schreibt einen `report.txt` mit gemessenen Gates; ein Befund schlägt eine Meinung.
- QR wird dekodiert (`kickoff.check_qr`), Lesbarkeit gemessen (`kickoff.legible`, Stufe A ≥ 0.95 für Sichtbares),
  Videos gegen Blitze geprüft (WCAG 2.3.1, `kickoff_loop_video.flash_check`).
- Nicht triviale Logik bekommt einen Selbsttest, der am **fertigen Bild** misst und am alten Fehler nachweislich anschlägt.

## Git

Repo `vadimitri/claude`. Hintergrund-Jobs arbeiten in `.claude/worktrees/<name>` auf eigenem Branch. Render-Ausgaben sind
gitignored (reproduzierbar aus Code + Config), Configs, Reports und kleine Referenzen nicht.
Stand 30.9.: der Hauptcheckout hat die Umstellung auf `src/` + `kickoff.py` + `editor/` noch nicht committet
(Snapshot davon: Commit 570c2f0 auf `claude/kickoff-loop`).

## Bekannte Schulden

- `src/styles.py` und `src/kickoff.py` haben Layout-Verhältnisse als nackte Zahlen im Code; beim Anfassen benennen.
- Der Verlaufs-Bug (Band über Zeilengrenzen) steckt noch in `styles.type_layers` (Maker Night, MAKER/NIGHT zweizeilig)
  und `kickoff.type_layers`; die Lösung ist `kickoff_loop.line_gradient`.
