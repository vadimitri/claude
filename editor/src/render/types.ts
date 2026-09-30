// Szene (UI -> CORE), siehe CONTRACT.md
export type Scene = {
  gw: number; gh: number;              // Zellraster
  W: number; H: number;                // Seite in Displaypixeln bei Export (A3 3504x4956, 9x16 1080x1920, 16x9 1920x1080, ...)
  cellPx: number;                      // Displaypixel pro Zelle beim Export (= R*u: 4 bei 1080p, 12 bei A3)
  pal: string[];                       // Palette dunkel->hell (data.pals[name])
  alt?: string[];                      // Zweitpalette fuer a2
  spark: string;                       // "S7"
  star: [number, number, number, number]; // x0, y0, R in m-Einheiten, rot Grad
  seed: number;
  titleMask: Uint8Array; textMask: Uint8Array;  // gw*gh, 0/1, Zeile fuer Zeile von oben
  titleBox: [number, number, number, number];   // m-Einheiten
  typeV: Float32Array;                 // gw*gh, Schriftwert 0..1 oder NaN = keine Schrift (inkl. CTA-Kasten in lvl(0))
  typeFlip: Uint8Array;                // 0 = nie kippen (CTA), 1 = pro Zelle kippen wo lit (Titel), 2 = pro Glyphe (Mehrheit, Kleintext)
  glyphId: Uint16Array;                // fuer typeFlip 2: Glyphen-Nummer (0 = keine)
  qr: { x: number; y: number; n: number; modules: Uint8Array } | null; // Platte in Zellen (links oben, Kantenlaenge n inkl. 3 Module Rand, Modul = 2 Zellen)
  glow: boolean;                       // Sternglow im Seitenhintergrund (styles.background)
};
