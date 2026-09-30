// default: Tx Ty 0.40 14
// default-wide: Tx Ty 0.40 14
// S31 "Gegenlicht" (lab_spark.c_gegenlicht): Stern hinter dem Titel, sein Licht bricht in Strahlen durch die Buchstabenluecken.
// Default = Titelmitte, R 0.40 fest.
float S31_ink(float d, float lo) { return lo + (1.0 - lo) * pow(clamp(1.0 - d, 0.0, 1.0), 0.7); }

// f-Intervall der Strecke c + (p - c) f (f in [0, 1]) innerhalb der Titel-Bbox (+2 Zellen): nur dort kann Schrift verdecken
vec2 S31_clip(vec2 p, vec2 c) {
  vec2 dir = p - c;
  dir = mix(dir, vec2(1e-6), lessThan(abs(dir), vec2(1e-6)));
  vec4 b = uTitleBox + vec4(-2.0, -2.0, 2.0, 2.0) * uCell;
  vec2 t1 = (b.xy - c) / dir, t2 = (b.zw - c) / dir;
  vec2 lo = min(t1, t2), hi = max(t1, t2);
  return vec2(max(max(lo.x, lo.y), 0.0), min(min(hi.x, hi.y), 1.0));
}

// lab_spark._lit_band (Plakatmodus): im Titel-/Datumsband kippt Schrift ab v >= 0.2, die Kopfzeile erst ab 0.5
float S31_litBand(vec2 p, float v) { return (p.y > uTitleBox.y - 0.025 ? v >= 0.2 : v >= 0.5) ? 1.0 : 0.0; }

vec4 spark_S31(vec2 p) {
  vec2 c = uStar.xy;
  float d = starMain(p);
  // radial(src, n=96, reach=0.97, decay=0.985) / max: Summe der Sternpixel (ohne Schrift) auf der Strecke p -> Stern,
  // Gewicht 0.985^s, f_s = 1 - s/96*0.97. Kontinuierlich in s, Schrift in <= 48 Schritten abgezogen.
  const float K = 0.985, N = 96.0, RE = 0.97;
  float lk = -log(K);
  float s0 = max(0.0, (1.0 - 1.0 / d) * N / RE);          // ab hier liegen die Proben im Stern
  float full = max(pow(K, s0) - pow(K, N), 0.0) / lk;
  vec2 fr = S31_clip(p, c);
  fr.x = max(fr.x, 1.0 - RE);
  fr.y = min(fr.y, 1.0 / max(d, 1e-6));
  float occ = 0.0;
  if (fr.y > fr.x) {
    float df = (fr.y - fr.x) / 48.0;
    for (int i = 0; i < 48; i++) {
      float f = fr.x + (float(i) + 0.5) * df;
      occ += titleMask(c + (p - c) * f) * pow(K, (1.0 - f) * N / RE);
    }
    occ *= df * N / RE;
  }
  float rays = max(full - occ, 0.0) / ((1.0 - pow(K, N)) / lk);
  float halo = exp(-length(p - c) / 0.45);                 // Streulicht: die ganze Titelzone steht im Gegenlicht
  float v = bg(p) + 0.95 * pow(rays, 0.8) + 0.3 * halo;
  if (d < 1.0) v = S31_ink(d, 0.75);
  v = clamp(v, 0.0, 1.0);
  return vec4(v, S31_litBand(p, v), 0.0, 0.0);
}
